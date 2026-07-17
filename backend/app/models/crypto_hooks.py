"""v1.0.2(GPT P0-6c): 字段级加密 SQLAlchemy 事件钩子。

对 User.email/phone 在写入时自动加密(AES-256-GCM), 读取时自动解密。
历史明文数据兼容: decrypt_field 对无前缀明文原样返回。

接入方式: 在 app 启动时 import 本模块即注册事件(lifespan 或 main.py)。
"""
from __future__ import annotations

import logging

from sqlalchemy import event

from app.models import User
from app.services.crypto_service import encrypt_field, decrypt_field

logger = logging.getLogger("srs.crypto")

_SENSITIVE_USER_FIELDS = ("email", "phone")


def _encrypt_user_fields(target, is_insert: bool):
    """before_insert/before_update: 加密 email/phone。"""
    for col in _SENSITIVE_USER_FIELDS:
        val = getattr(target, col, None)
        if val is None or val == "":
            continue
        val_str = str(val)
        # 已加密(有 AES:/B64: 前缀)则跳过, 避免重复加密
        if val_str.startswith(("AES:", "B64:")):
            continue
        try:
            encrypted = encrypt_field(val_str)
            setattr(target, col, encrypted)
        except Exception as e:  # noqa: BLE001
            # 加密失败不阻断写入(降级为明文), 但记录错误
            logger.error(f"加密 {col} 失败, 降级明文: {e}")


def _decrypt_user_fields(target):
    """after_load/__init__: 解密 email/phone。"""
    for col in _SENSITIVE_USER_FIELDS:
        val = getattr(target, col, None)
        if val is None or val == "":
            continue
        val_str = str(val)
        # 只有加密前缀的才解密
        if not val_str.startswith(("AES:", "B64:")):
            continue
        try:
            decrypted = decrypt_field(val_str)
            if decrypted is not None:
                setattr(target, col, decrypted)
        except Exception as e:  # noqa: BLE001
            logger.error(f"解密 {col} 失败: {e}")


# 注册事件
event.listen(User, "before_insert", lambda target, *_: _encrypt_user_fields(target, True))
event.listen(User, "before_update", lambda target, *_: _encrypt_user_fields(target, False))
event.listen(User, "load", lambda target, *_: _decrypt_user_fields(target))


def init_crypto_hooks():
    """显式初始化(确保事件已注册)。在 main.py lifespan 调用。

    event.listen 在模块 import 时已注册, 此函数仅供显式初始化确认。
    """
    logger.info("字段加密钩子已注册: User.email/phone")
