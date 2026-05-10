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


def parse_csv(content: str) -> list[ParsedLine]:
    """Parse CSV with Character,Dialogue columns."""
    lines = []
    reader = csv.reader(io.StringIO(content))
    header = next(reader, None)

    # Detect header
    if header and header[0].strip().lower() in ("character", "name", "speaker"):
        pass  # skip header
    else:
        # No header, treat first row as data
        if header and len(header) >= 2:
            clean, dirs, pause = _extract_directives(header[1].strip())
            lines.append(ParsedLine(1, header[0].strip(), clean, header[1].strip(), dirs, pause))

    for i, row in enumerate(reader, start=len(lines) + 1):
        if len(row) >= 2 and row[0].strip() and row[1].strip():
            clean, dirs, pause = _extract_directives(row[1].strip())
            lines.append(ParsedLine(i, row[0].strip(), clean, row[1].strip(), dirs, pause))

    return lines


def parse_txt(content: str) -> list[ParsedLine]:
    """Parse TXT with 'Character: Dialogue' format."""
    lines = []
    for i, raw_line in enumerate(content.strip().split('\n'), start=1):
        raw_line = raw_line.strip()
        if not raw_line or ':' not in raw_line:
            continue
        parts = raw_line.split(':', 1)
        character = parts[0].strip()
        dialogue = parts[1].strip().strip('"').strip("'")
        if character and dialogue:
            clean, dirs, pause = _extract_directives(dialogue)
            lines.append(ParsedLine(i, character, clean, dialogue, dirs, pause))

    return lines


def parse_json(content: str) -> list[ParsedLine]:
    """Parse JSON array of {character, dialogue} objects."""
    data = json.loads(content)
    lines = []
    if isinstance(data, list):
        for i, item in enumerate(data, start=1):
            char = item.get("character", item.get("name", item.get("speaker", "")))
            text = item.get("dialogue", item.get("text", item.get("line", "")))
            if char and text:
                clean, dirs, pause = _extract_directives(text)
                lines.append(ParsedLine(i, char, clean, text, dirs, pause))
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
