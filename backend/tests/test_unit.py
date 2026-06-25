"""DialogueForge tests."""

import pytest
import hashlib
from unittest.mock import AsyncMock, patch, MagicMock

# ---- Script Parser Tests ----

from app.services.script_parser import parse_csv, parse_txt, _extract_directives


class TestScriptParser:
    def test_parse_csv_basic(self):
        csv_data = "Character,Dialogue\nCommander,Move out!\nPilot,Copy that."
        lines = parse_csv(csv_data)
        assert len(lines) == 2
        assert lines[0].character_name == "Commander"
        assert lines[0].text == "Move out!"
        assert lines[1].character_name == "Pilot"

    def test_parse_csv_with_directives(self):
        csv_data = 'Character,Dialogue\nPilot,"[radio] Mayday mayday!"'
        lines = parse_csv(csv_data)
        assert lines[0].character_name == "Pilot"
        assert "radio" in lines[0].directives

    def test_parse_txt(self):
        txt = "Commander: All units advance.\nPilot: Roger that."
        lines = parse_txt(txt)
        assert len(lines) == 2
        assert lines[0].character_name == "Commander"

    def test_extract_directives(self):
        text = "[radio] Hello [pause:1.5] world [angry]"
        clean, directives, pause_ms = _extract_directives(text)
        assert "radio" in directives
        assert "angry" in directives
        assert pause_ms == 1500
        assert "[radio]" not in clean

    def test_extract_no_directives(self):
        text = "Just normal text here"
        clean, directives, pause_ms = _extract_directives(text)
        assert directives == []
        assert pause_ms == 0
        assert clean == text


# ---- Security Tests ----

from app.core.security import encrypt_api_key, decrypt_api_key


class TestSecurity:
    def test_encrypt_decrypt_roundtrip(self):
        key = "sk_test_abc123xyz"
        encrypted = encrypt_api_key(key)
        assert encrypted != key
        decrypted = decrypt_api_key(encrypted)
        assert decrypted == key

    def test_different_encryptions(self):
        key = "sk_test_same"
        e1 = encrypt_api_key(key)
        e2 = encrypt_api_key(key)
        # Fernet uses random IV so ciphertexts differ
        # but both decrypt to the same value
        assert decrypt_api_key(e1) == decrypt_api_key(e2) == key


# ---- Effects Tests ----

from app.audio.effects import EFFECT_PRESETS


class TestEffects:
    def test_all_presets_exist(self):
        expected = {"radio", "helmet", "robot", "telephone", "megaphone",
                    "vhs", "corrupted_ai", "deep_space", "glitch", "alien"}
        assert expected.issubset(set(EFFECT_PRESETS.keys()))

    def test_presets_are_strings(self):
        for name, filt in EFFECT_PRESETS.items():
            assert isinstance(filt, str)
            assert len(filt) > 0


# ---- Config Tests ----

from app.core.config import Settings


class TestConfig:
    def test_defaults(self):
        s = Settings()
        assert s.app_name == "DialogueForge"
        assert s.default_sample_rate == 44100
        assert s.max_concurrent_generations > 0

    def test_cors_origins(self):
        s = Settings()
        assert isinstance(s.cors_origins, list)


# ---- ElevenLabs Service Tests ----

from app.services.elevenlabs import ElevenLabsService


class TestElevenLabsService:
    def test_compute_cache_key(self):
        k1 = ElevenLabsService.compute_cache_key("hello", "voice1", "model1", 0.5, 0.5, 0.0)
        k2 = ElevenLabsService.compute_cache_key("hello", "voice1", "model1", 0.5, 0.5, 0.0)
        k3 = ElevenLabsService.compute_cache_key("hello", "voice2", "model1", 0.5, 0.5, 0.0)
        assert k1 == k2
        assert k1 != k3

    def test_cache_key_deterministic(self):
        key = ElevenLabsService.compute_cache_key("text", "vid", "mid", 0.5, 0.75, 0.0)
        assert isinstance(key, str)
        assert len(key) == 64  # SHA-256 hex digest


# ---- Timecode + Timeline Tests ----

from app.services.script_parser import parse_timecode, format_timecode, parse_csv, parse_txt, parse_json


class TestTimecode:
    def test_parse_mss(self):
        assert parse_timecode("0:00") == 0
        assert parse_timecode("1:23") == 83000
        assert parse_timecode("0:05") == 5000

    def test_parse_fractional(self):
        assert parse_timecode("0:02.5") == 2500

    def test_parse_hms(self):
        assert parse_timecode("1:02:03") == 3723000

    def test_parse_plain_seconds(self):
        assert parse_timecode("12") == 12000

    def test_parse_empty_returns_none(self):
        assert parse_timecode("") is None
        assert parse_timecode("   ") is None
        assert parse_timecode(None) is None

    def test_parse_invalid_returns_none(self):
        assert parse_timecode("abc") is None

    def test_format_roundtrip(self):
        assert format_timecode(0) == "0:00"
        assert format_timecode(83000) == "1:23"
        assert format_timecode(5000) == "0:05"


class TestCSVOptionalColumns:
    def test_start_column(self):
        csv = "Character,Dialogue,Start\nA,Hi,0:05\nB,Yo,0:10"
        lines = parse_csv(csv)
        assert lines[0].start_time_ms == 5000
        assert lines[1].start_time_ms == 10000

    def test_all_columns(self):
        csv = "Character,Dialogue,Start,Volume,Effect\nA,Hi,0:05,-3,radio"
        lines = parse_csv(csv)
        assert lines[0].start_time_ms == 5000
        assert lines[0].volume_adjust_db == -3.0
        assert lines[0].effect_override == "radio"

    def test_backward_compat_two_column(self):
        csv = "Character,Dialogue\nA,Hi\nB,Bye"
        lines = parse_csv(csv)
        assert len(lines) == 2
        assert lines[0].start_time_ms is None
        assert lines[0].volume_adjust_db == 0.0

    def test_column_order_independence(self):
        csv = "Effect,Character,Start,Dialogue\nradio,A,0:03,Hello"
        lines = parse_csv(csv)
        assert lines[0].character_name == "A"
        assert lines[0].text == "Hello"
        assert lines[0].start_time_ms == 3000
        assert lines[0].effect_override == "radio"


class TestTimelineConcat:
    def test_timeline_placement(self, tmp_path):
        import asyncio
        from pydub import AudioSegment
        from app.audio.effects import concatenate_audio_timeline, get_audio_duration_ms

        # Make three 1-second clips
        paths = []
        for i in range(3):
            p = str(tmp_path / f"c{i}.wav")
            AudioSegment.silent(duration=1000, frame_rate=44100).export(p, format="wav")
            paths.append(p)

        clips = [
            {"path": paths[0], "start_ms": 0, "pause_after_ms": 0},
            {"path": paths[1], "start_ms": 5000, "pause_after_ms": 0},
            {"path": paths[2], "start_ms": 10000, "pause_after_ms": 0},
        ]
        out = str(tmp_path / "out.wav")
        asyncio.run(concatenate_audio_timeline(clips, out, silence_ms=500))
        dur = get_audio_duration_ms(out)
        # Last clip starts at 10s, lasts 1s -> ~11s total
        assert 10900 <= dur <= 11100, dur


class TestVoiceColumns:
    def test_elevenlabs_and_chatterbox_columns(self):
        csv = ("Character,Dialogue,ElevenLabs,Chatterbox\n"
               "Mary,Hello,21m00Tcm4TlvDq8ikWAM,my_clone\n"
               "John,Hi there,AZnzlk1XvdvUeBnXmlld,")
        lines = parse_csv(csv)
        assert lines[0].elevenlabs_voice == "21m00Tcm4TlvDq8ikWAM"
        assert lines[0].chatterbox_voice == "my_clone"
        assert lines[1].elevenlabs_voice == "AZnzlk1XvdvUeBnXmlld"
        assert lines[1].chatterbox_voice == ""

    def test_voice_columns_optional(self):
        csv = "Character,Dialogue\nMary,Hello"
        lines = parse_csv(csv)
        assert lines[0].elevenlabs_voice == ""
        assert lines[0].chatterbox_voice == ""

    def test_voice_column_aliases(self):
        csv = ("Character,Dialogue,eleven,cb_voice\n"
               "A,Hi,voice123,clone1")
        lines = parse_csv(csv)
        assert lines[0].elevenlabs_voice == "voice123"
        assert lines[0].chatterbox_voice == "clone1"


class TestSpreadsheetTimecodeArtifact:
    def test_mmss_with_spurious_zero_seconds(self):
        # Google Sheets exports "24:08" (MM:SS) as "24:08:00" (HH:MM:SS)
        assert parse_timecode("24:08:00") == 1448000   # 24m08s
        assert parse_timecode("33:36:00") == 2016000   # 33m36s

    def test_genuine_hms_preserved(self):
        # Real H:MM:SS under 2 hours stays as-is
        assert parse_timecode("1:02:03") == 3723000
        assert parse_timecode("0:02:00") == 120000     # 2 minutes

    def test_two_part_unaffected(self):
        assert parse_timecode("23:59") == 1439000

    def test_effect_lowercased(self):
        csv = "Character,Dialogue,Effect\nA,Hi,Telephone\nB,Yo,RADIO"
        lines = parse_csv(csv)
        assert lines[0].effect_override == "telephone"
        assert lines[1].effect_override == "radio"
