"""飞书事件订阅 - 解密 + 签名验证 (V2)。

参考: https://open.feishu.cn/document/server-docs/event-subscription-guide/overview
- 加密: AES-256-CBC, key = sha256(encrypt_key)
- 签名: sha256(timestamp + nonce + encrypt_key + body)
"""

from __future__ import annotations

import base64
import hashlib
import json
from typing import Any

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes


class EventVerificationError(Exception):
    """签名或解密失败。"""


def _derive_key(encrypt_key: str) -> bytes:
    return hashlib.sha256(encrypt_key.encode("utf-8")).digest()


def decrypt_payload(encrypted_b64: str, encrypt_key: str) -> dict[str, Any]:
    """解密飞书事件 body 中的 encrypt 字段, 返回解密后的 JSON dict。

    算法:
        iv = ciphertext[:16]
        data = AES-256-CBC.decrypt(key=sha256(encrypt_key), iv=iv, ct=ciphertext[16:])
        移除 PKCS7 padding, 再 json.loads
    """
    try:
        raw = base64.b64decode(encrypted_b64)
        iv = raw[:16]
        ciphertext = raw[16:]
        key = _derive_key(encrypt_key)
        cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
        decryptor = cipher.decryptor()
        padded = decryptor.update(ciphertext) + decryptor.finalize()
        # 去除 PKCS7 padding
        pad_len = padded[-1]
        if pad_len < 1 or pad_len > 16:
            raise EventVerificationError("invalid PKCS7 padding length")
        plain = padded[:-pad_len]
        return json.loads(plain.decode("utf-8"))  # type: ignore[no-any-return]
    except EventVerificationError:
        raise
    except Exception as e:
        raise EventVerificationError(f"decrypt failed: {e}") from e


def verify_signature(
    timestamp: str,
    nonce: str,
    encrypt_key: str,
    raw_body: bytes,
    signature_header: str,
) -> bool:
    """飞书 V2 事件签名校验。

    signature = sha256(timestamp + nonce + encrypt_key + raw_body_bytes).hexdigest()
    """
    if not signature_header:
        return False
    h = hashlib.sha256()
    h.update(timestamp.encode("utf-8"))
    h.update(nonce.encode("utf-8"))
    h.update(encrypt_key.encode("utf-8"))
    h.update(raw_body)
    expected = h.hexdigest()
    # 固定时间比较, 防止时序攻击
    return _constant_time_eq(expected, signature_header.strip())


def _constant_time_eq(a: str, b: str) -> bool:
    if len(a) != len(b):
        return False
    result = 0
    for x, y in zip(a, b, strict=True):
        result |= ord(x) ^ ord(y)
    return result == 0


def extract_event_id(payload: dict[str, Any]) -> str | None:
    """从解密后的 payload 提取 event_id, 用于幂等去重。"""
    header = payload.get("header", {})
    return header.get("event_id")  # type: ignore[no-any-return]


def extract_event_type(payload: dict[str, Any]) -> str | None:
    header = payload.get("header", {})
    return header.get("event_type")  # type: ignore[no-any-return]
