"""测试 webhook 解密与签名验证。"""

from __future__ import annotations

import base64
import hashlib
import json

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from meeting_bot.feishu.events import (
    decrypt_payload,
    extract_event_id,
    extract_event_type,
    verify_signature,
)


def _encrypt(plaintext: dict, key_str: str) -> str:
    """测试辅助: 按飞书算法加密 payload。"""
    key = hashlib.sha256(key_str.encode()).digest()
    iv = b"0123456789abcdef"
    data = json.dumps(plaintext, ensure_ascii=False).encode("utf-8")
    pad_len = 16 - (len(data) % 16)
    data += bytes([pad_len]) * pad_len
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
    encryptor = cipher.encryptor()
    ct = encryptor.update(data) + encryptor.finalize()
    return base64.b64encode(iv + ct).decode("ascii")


def test_decrypt_roundtrip() -> None:
    key = "0123456789abcdef0123456789abcdef"
    original = {
        "schema": "2.0",
        "header": {"event_id": "evt_xyz", "event_type": "vc.meeting.meeting_ended_v1"},
        "event": {"meeting_id": "123"},
    }
    encrypted = _encrypt(original, key)
    decrypted = decrypt_payload(encrypted, key)
    assert decrypted == original


def test_extract_event_header() -> None:
    payload = {
        "header": {"event_id": "evt_123", "event_type": "minutes.minute.created_v1"},
        "event": {},
    }
    assert extract_event_id(payload) == "evt_123"
    assert extract_event_type(payload) == "minutes.minute.created_v1"


def test_signature_verification() -> None:
    key = "0123456789abcdef0123456789abcdef"
    ts = "1712000000"
    nonce = "abc123"
    body = b'{"encrypt":"xxx"}'

    h = hashlib.sha256()
    h.update(ts.encode())
    h.update(nonce.encode())
    h.update(key.encode())
    h.update(body)
    valid = h.hexdigest()

    assert verify_signature(ts, nonce, key, body, valid) is True
    assert verify_signature(ts, nonce, key, body, "wrong") is False
    assert verify_signature(ts, nonce, key, b"tampered", valid) is False
