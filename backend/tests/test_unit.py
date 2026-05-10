"""DialogueForge tests."""

import pytest
import hashlib
from unittest.mock import AsyncMock, patch, MagicMock

# ---- Script Parser Tests ----

from app.services.script_parser import parse_csv_content, parse_txt_content, extract_directives


class TestScriptParser:
    def test_parse_csv_basic(self):
        csv_data = "Character,Dialogue\nCommander,Move out!\nPilot,Copy that."
        lines = parse_csv_content(csv_data)
        assert len(lines) == 2
        assert lines[0]["character_name"] == "Commander"
        assert lines[0]["text"] == "Move out!"
        assert lines[1]["character_name"] == "Pilot"

    def test_parse_csv_with_directives(self):
        csv_data = 'Character,Dialogue\nPilot,"[radio] Mayday mayday!"'
        lines = parse_csv_content(csv_data)
        assert lines[0]["character_name"] == "Pilot"
        assert "radio" in lines[0]["directives"]

    def test_parse_txt(self):
        txt = "Commander: All units advance.\nPilot: Roger that."
        lines = parse_txt_content(txt)
        assert len(lines) == 2
        assert lines[0]["character_name"] == "Commander"

    def test_extract_directives(self):
        text = "[radio] Hello [pause:1.5] world [angry]"
        result = extract_directives(text)
        assert "radio" in result["directives"]
        assert "angry" in result["directives"]
        assert result["pause_ms"] == 1500
        assert "[radio]" not in result["clean_text"]

    def test_extract_no_directives(self):
        text = "Just normal text here"
        result = extract_directives(text)
        assert result["directives"] == []
        assert result["pause_ms"] == 0
        assert result["clean_text"] == text


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

from app.audio.effects import EFFECT_PRESETS, build_ffmpeg_filter


class TestEffects:
    def test_all_presets_exist(self):
        expected = {"radio", "helmet", "robot", "telephone", "megaphone",
                    "vhs", "corrupted_ai", "deep_space", "glitch", "alien"}
        assert expected.issubset(set(EFFECT_PRESETS.keys()))

    def test_build_filter_returns_string(self):
        for name in EFFECT_PRESETS:
            filt = build_ffmpeg_filter(name)
            assert isinstance(filt, str)
            assert len(filt) > 0


# ---- Config Tests ----

from app.core.config import Settings


class TestConfig:
    def test_defaults(self):
        s = Settings()
        assert s.APP_NAME == "DialogueForge"
        assert s.SAMPLE_RATE == 44100
        assert s.MAX_CONCURRENT_REQUESTS > 0

    def test_cors_origins(self):
        s = Settings()
        assert isinstance(s.CORS_ORIGINS, list)


# ---- ElevenLabs Service Tests ----

from app.services.elevenlabs import ElevenLabsService


class TestElevenLabsService:
    def test_compute_cache_key(self):
        svc = ElevenLabsService.__new__(ElevenLabsService)
        k1 = svc.compute_cache_key("hello", "voice1", {"stability": 0.5})
        k2 = svc.compute_cache_key("hello", "voice1", {"stability": 0.5})
        k3 = svc.compute_cache_key("hello", "voice2", {"stability": 0.5})
        assert k1 == k2
        assert k1 != k3

    def test_cache_key_deterministic(self):
        svc = ElevenLabsService.__new__(ElevenLabsService)
        key = svc.compute_cache_key("text", "vid", {"a": 1, "b": 2})
        assert isinstance(key, str)
        assert len(key) == 64  # SHA-256 hex digest
