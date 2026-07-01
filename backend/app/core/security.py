"""密码哈希与 JWT。密码必须哈希存储, 禁止明文。

直接使用 bcrypt (passlib 在 Python 3.13 不兼容, 已弃用)。
"""
import re
from datetime import datetime, timedelta, timezone

import bcrypt
from jose import jwt, JWTError

from app.core.config import get_settings


def hash_password(raw: str) -> str:
    return bcrypt.hashpw(raw.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(raw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(raw.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        return False


def validate_password_strength(pw: str) -> tuple[bool, str]:
    """密码强度校验: ≥8位, 大小写字母+数字+特殊字符 至少3类。返回 (通过, 失败原因)。"""
    if len(pw) < 8:
        return False, "密码至少 8 位"
    categories = 0
    if re.search(r"[A-Z]", pw):
        categories += 1
    if re.search(r"[a-z]", pw):
        categories += 1
    if re.search(r"[0-9]", pw):
        categories += 1
    if re.search(r"[^A-Za-z0-9]", pw):
        categories += 1
    if categories < 3:
        return False, "密码需包含大写字母、小写字母、数字、特殊字符中至少 3 类"
    return True, ""


def create_access_token(subject: str, extra: dict | None = None) -> str:
    s = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(minutes=s.access_token_expire_minutes)
    payload = {"sub": subject, "exp": expire}
    if extra:
        payload.update(extra)
    return jwt.encode(payload, s.secret_key, algorithm=s.algorithm)


def generate_reset_token(user_id: int) -> str:
    """短期 JWT (15min), 用途=重置密码。"""
    s = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    payload = {"sub": str(user_id), "exp": expire, "purpose": "reset_password"}
    return jwt.encode(payload, s.secret_key, algorithm=s.algorithm)


def verify_reset_token(token: str) -> int | None:
    """验证重置令牌, 成功返回 user_id, 失败返回 None。"""
    s = get_settings()
    try:
        payload = jwt.decode(token, s.secret_key, algorithms=[s.algorithm])
    except JWTError:
        return None
    if payload.get("purpose") != "reset_password":
        return None
    try:
        return int(payload["sub"])
    except (ValueError, KeyError):
        return None
