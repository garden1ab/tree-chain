"""Parse dialogue scripts from CSV, TXT, and JSON formats."""

import csv
import io
import json
import re
from dataclasses import dataclass


@dataclass
class ParsedLine:
    line_number: int
    character_name: str
    text: str
    raw_text: str
    directives: list[str]
    pause_after_ms: int = 0
    start_time_ms: int | None = None  # absolute placement on combined timeline (None = auto/sequential)
    volume_adjust_db: float = 0.0     # per-line volume tweak in dB
    effect_override: str = ""         # per-line effect preset override (blank = use character default)
    elevenlabs_voice: str = ""        # ElevenLabs voice_id for this character (column hint)
    chatterbox_voice: str = ""        # Chatterbox voice name for this character (column hint)


def parse_timecode(value: str) -> int | None:
    """Parse a timecode like '0:00', '1:23', '1:23.5', or plain seconds '12'.

    Returns milliseconds, or None if empty/invalid.
    Formats supported:
      M:SS        -> minutes:seconds       (e.g. 1:30 -> 90000)
      M:SS.mmm    -> with fractional secs  (e.g. 0:02.5 -> 2500)
      H:MM:SS     -> hours:minutes:seconds (e.g. 1:02:03)
      SS          -> plain seconds         (e.g. 12 -> 12000)
    """
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None
    try:
        parts = value.split(":")
        if len(parts) == 1:
            return int(round(float(parts[0]) * 1000))
        elif len(parts) == 2:
            minutes = int(parts[0])
            seconds = float(parts[1])
            return int(round((minutes * 60 + seconds) * 1000))
        elif len(parts) == 3:
            hours = int(parts[0])
            minutes = int(parts[1])
            seconds = float(parts[2])
            return int(round((hours * 3600 + minutes * 60 + seconds) * 1000))
    except (ValueError, IndexError):
        return None
    return None


def format_timecode(ms: int) -> str:
    """Format milliseconds back to M:SS (or H:MM:SS for >= 1 hour)."""
    if ms is None:
        return ""
    total_seconds = ms / 1000.0
    hours = int(total_seconds // 3600)
    minutes = int((total_seconds % 3600) // 60)
    seconds = total_seconds % 60
    if hours > 0:
        return f"{hours}:{minutes:02d}:{int(seconds):02d}"
    if seconds == int(seconds):
        return f"{minutes}:{int(seconds):02d}"
    return f"{minutes}:{seconds:05.2f}"


def _extract_directives(text: str) -> tuple[str, list[str], int]:
    """Extract [tags] from dialogue text. Returns (clean_text, directives, pause_ms)."""
    directives = []
    pause_ms = 0
    clean = text

    tags = re.findall(r'\[([^\]]+)\]', text)
    for tag in tags:
        if tag.startswith("pause:"):
            try:
                pause_ms = int(float(tag.split(":")[1]) * 1000)
            except (ValueError, IndexError):
                pass
        else:
            directives.append(tag)
        clean = clean.replace(f"[{tag}]", "").strip()

    clean = re.sub(r'\s+', ' ', clean).strip()
    return clean, directives, pause_ms


# Column-name aliases for flexible CSV headers
CHARACTER_COLS = {"character", "name", "speaker", "char"}
DIALOGUE_COLS = {"dialogue", "text", "line", "speech"}
START_COLS = {"start", "start_time", "starttime", "time", "timecode", "cue", "timestamp"}
PAUSE_COLS = {"pause", "pause_after", "delay", "gap"}
VOLUME_COLS = {"volume", "vol", "gain", "volume_db"}
EFFECT_COLS = {"effect", "effects", "preset", "fx"}
ELEVENLABS_COLS = {"elevenlabs", "elevenlabs_voice", "eleven_labs", "el_voice", "elvoice", "eleven"}
CHATTERBOX_COLS = {"chatterbox", "chatterbox_voice", "cb_voice", "cbvoice"}


def parse_csv(content: str) -> list[ParsedLine]:
    """Parse CSV. Required: Character, Dialogue.
    Optional columns (any order, case-insensitive headers):
      Start    - timecode for placement in combined audio (e.g. 0:00, 1:23)
      Pause    - seconds of silence to add after this line
      Volume   - per-line volume adjustment in dB (e.g. -3, 2.5)
      Effect   - per-line effect preset override
    """
    reader = csv.reader(io.StringIO(content))
    rows = list(reader)
    if not rows:
        return []

    header = rows[0]
    header_lower = [h.strip().lower() for h in header]
    has_header = any(h in CHARACTER_COLS for h in header_lower)

    col = {"character": 0, "dialogue": 1, "start": None,
           "pause": None, "volume": None, "effect": None,
           "elevenlabs": None, "chatterbox": None}

    if has_header:
        for idx, h in enumerate(header_lower):
            if h in CHARACTER_COLS:
                col["character"] = idx
            elif h in DIALOGUE_COLS:
                col["dialogue"] = idx
            elif h in START_COLS:
                col["start"] = idx
            elif h in PAUSE_COLS:
                col["pause"] = idx
            elif h in VOLUME_COLS:
                col["volume"] = idx
            elif h in EFFECT_COLS:
                col["effect"] = idx
            elif h in ELEVENLABS_COLS:
                col["elevenlabs"] = idx
            elif h in CHATTERBOX_COLS:
                col["chatterbox"] = idx
        data_rows = rows[1:]
    else:
        if len(header) >= 3:
            col["start"] = 2
        data_rows = rows

    def get(row, key):
        idx = col[key]
        if idx is None or idx >= len(row):
            return ""
        return row[idx].strip()

    lines = []
    n = 0
    for row in data_rows:
        if not row:
            continue
        character = get(row, "character")
        dialogue_raw = get(row, "dialogue")
        if not character or not dialogue_raw:
            continue
        n += 1

        clean, dirs, pause = _extract_directives(dialogue_raw)

        start_ms = parse_timecode(get(row, "start")) if col["start"] is not None else None

        pause_col_val = get(row, "pause") if col["pause"] is not None else ""
        if pause_col_val:
            parsed_pause = parse_timecode(pause_col_val)
            if parsed_pause is not None:
                pause = parsed_pause

        vol_db = 0.0
        vol_val = get(row, "volume") if col["volume"] is not None else ""
        if vol_val:
            try:
                vol_db = float(vol_val)
                # Clamp to a sane range to avoid silence/distortion
                vol_db = max(-40.0, min(20.0, vol_db))
            except ValueError:
                pass

        effect = get(row, "effect") if col["effect"] is not None else ""
        el_voice = get(row, "elevenlabs") if col["elevenlabs"] is not None else ""
        cb_voice = get(row, "chatterbox") if col["chatterbox"] is not None else ""

        lines.append(ParsedLine(
            line_number=n,
            character_name=character,
            text=clean,
            raw_text=dialogue_raw,
            directives=dirs,
            pause_after_ms=pause,
            start_time_ms=start_ms,
            volume_adjust_db=vol_db,
            effect_override=effect,
            elevenlabs_voice=el_voice,
            chatterbox_voice=cb_voice,
        ))

    return lines


def parse_txt(content: str) -> list[ParsedLine]:
    """Parse TXT with 'Character: Dialogue' format.

    Optional leading timecode supported:  [0:15] Character: Dialogue
    """
    lines = []
    n = 0
    for raw_line in content.strip().split('\n'):
        raw_line = raw_line.strip()
        if not raw_line or ':' not in raw_line:
            continue

        start_ms = None
        tc_match = re.match(r'^\[(\d+:\d+(?::\d+)?(?:\.\d+)?)\]\s*(.*)$', raw_line)
        if tc_match:
            start_ms = parse_timecode(tc_match.group(1))
            raw_line = tc_match.group(2)

        if ':' not in raw_line:
            continue
        parts = raw_line.split(':', 1)
        character = parts[0].strip()
        dialogue = parts[1].strip().strip('"').strip("'")
        if character and dialogue:
            n += 1
            clean, dirs, pause = _extract_directives(dialogue)
            lines.append(ParsedLine(
                line_number=n, character_name=character, text=clean,
                raw_text=dialogue, directives=dirs, pause_after_ms=pause,
                start_time_ms=start_ms,
            ))

    return lines


def parse_json(content: str) -> list[ParsedLine]:
    """Parse JSON array of objects.
    Recognized keys: character/name/speaker, dialogue/text/line,
    start/start_time (timecode str or ms int), pause/pause_after (seconds),
    volume (dB), effect (preset name).
    """
    data = json.loads(content)
    lines = []
    if isinstance(data, list):
        n = 0
        for item in data:
            char = item.get("character", item.get("name", item.get("speaker", "")))
            text = item.get("dialogue", item.get("text", item.get("line", "")))
            if not char or not text:
                continue
            n += 1
            clean, dirs, pause = _extract_directives(text)

            start_raw = item.get("start", item.get("start_time"))
            if isinstance(start_raw, (int, float)):
                start_ms = int(start_raw)
            elif isinstance(start_raw, str):
                start_ms = parse_timecode(start_raw)
            else:
                start_ms = None

            pause_raw = item.get("pause", item.get("pause_after"))
            if isinstance(pause_raw, (int, float)):
                pause = int(pause_raw * 1000)
            elif isinstance(pause_raw, str):
                pp = parse_timecode(pause_raw)
                if pp is not None:
                    pause = pp

            vol_db = 0.0
            try:
                vol_db = float(item.get("volume", 0.0))
            except (ValueError, TypeError):
                pass

            effect = str(item.get("effect", "") or "")

            lines.append(ParsedLine(
                line_number=n, character_name=char, text=clean,
                raw_text=text, directives=dirs, pause_after_ms=pause,
                start_time_ms=start_ms, volume_adjust_db=vol_db,
                effect_override=effect,
            ))
    return lines


def parse_script(content: str, filename: str) -> list[ParsedLine]:
    """Route to the correct parser based on file extension."""
    ext = filename.lower().rsplit('.', 1)[-1] if '.' in filename else 'txt'
    if ext == 'csv':
        return parse_csv(content)
    elif ext == 'json':
        return parse_json(content)
    else:
        return parse_txt(content)
