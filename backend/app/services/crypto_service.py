#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""v1.0.2: 字段级 AES-256 加密服务(GPT 第九节 + 裴总决策: 本轮实现)。

用途: 加密敏感字段(经纬度精确值/联系方式/用户PII)。
密钥: 从 AppData 派生(PBKDF2), 不入仓库。
算法: AES-256-GCM(认证加密)。
"""
from __future__ import annotations

import base64
import hashlib
import os
import json
from pathlib import Path


def _get_app_data_dir() -> Path:
    """返回 AppData/SRS 目录。"""
    if os.name == 'nt':
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
    elif os.sys.platform == 'darwin':
        base = os.path.expanduser("~/Library/Application Support")
    else:
        base = os.environ.get("XDG_DATA_HOME", os.path.expanduser("~/.local/share"))
    p = Path(base) / "SRS"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _derive_key(password: str | None = None, salt: bytes | None = None) -> tuple[bytes, bytes]:
    """PBKDF2 派生 256 位密钥。"""
    if salt is None:
        salt_file = _get_app_data_dir() / ".salt"
        if salt_file.exists():
            salt = salt_file.read_bytes()
        else:
            salt = os.urandom(16)
            salt_file.write_bytes(salt)
            salt_file.chmod(0o600)
    # 密码: 用户传入或机器特征
    if password is None:
        import getpass
        machine = os.environ.get("COMPUTERNAME", os.environ.get("HOSTNAME", "srs-default"))
        user = getpass.getuser()
        password = f"{machine}-{user}-srs-key-v1.0.2"
    key = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, iterations=100000, dklen=32)
    return key, salt


def encrypt_field(plaintext: str, key: bytes | None = None) -> str:
    """加密字段值, 返回 base64(ciphertext + nonce + tag)。

    使用 AES-256-GCM(需 cryptography 库)。
    """
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    except ImportError:
        # 无 cryptography 库时降级(非生产), 返回 base64(明文) + 标记
        return "B64:" + base64.b64encode(plaintext.encode()).decode()

    if key is None:
        key, _ = _derive_key()

    nonce = os.urandom(12)
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode('utf-8'), None)
    # 组合 nonce + ciphertext, base64 编码
    combined = nonce + ciphertext
    return "AES:" + base64.b64encode(combined).decode()


def decrypt_field(encrypted: str, key: bytes | None = None) -> str:
    """解密字段值。"""
    if encrypted.startswith("B64:"):
        return base64.b64decode(encrypted[4:]).decode('utf-8')

    if not encrypted.startswith("AES:"):
        return encrypted  # 未加密的明文

    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    except ImportError:
        raise RuntimeError("解密需要 cryptography 库")

    if key is None:
        key, _ = _derive_key()

    combined = base64.b64decode(encrypted[4:])
    nonce = combined[:12]
    ciphertext = combined[12:]
    aesgcm = AESGCM(key)
    return aesgcm.decrypt(nonce, ciphertext, None).decode('utf-8')


# 需要加密的敏感字段配置
SENSITIVE_FIELDS = {
    "sites": ["longitude", "latitude"],  # 精确经纬度
    "users": ["contact_email", "contact_phone"],
    "system_config": ["admin_contact_phone", "admin_contact_email"],
}


def is_sensitive(table: str, column: str) -> bool:
    """判断字段是否敏感需加密。"""
    return column in SENSITIVE_FIELDS.get(table, [])
