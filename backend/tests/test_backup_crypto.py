#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""GPT 审计第九节: 加密/备份/恢复测试。"""
import os
import sys
import pytest

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND)


@pytest.fixture
def fresh_db():
    from app.db.session import SessionLocal, reset_engine_for_tests
    from app.models import Base
    from app.db import session as _session_mod
    reset_engine_for_tests("sqlite:///./srs_test_session.db")
    Base.metadata.drop_all(bind=_session_mod.engine)
    Base.metadata.create_all(bind=_session_mod.engine)
    from app.db.seed_db import seed_if_empty
    seed_if_empty()
    return SessionLocal()


def test_aes_encrypt_decrypt(fresh_db):
    """AES-256-GCM 加密/解密(GPT 9.2)。"""
    from app.services.crypto_service import encrypt_field, decrypt_field
    plaintext = "116.4074,39.9042"  # 精确经纬度
    encrypted = encrypt_field(plaintext)
    assert encrypted.startswith("AES:"), "加密结果应以 AES: 开头"
    decrypted = decrypt_field(encrypted)
    assert decrypted == plaintext, "解密应还原明文"
    # 不同次加密结果不同(nonce 随机)
    enc2 = encrypt_field(plaintext)
    assert enc2 != encrypted, "AES-GCM nonce 应随机"


def test_sensitive_field_detection():
    """敏感字段识别。v1.0.2(P0-6c): sites经纬度加密留后续版本(Numeric类型限制)。"""
    from app.services.crypto_service import is_sensitive
    # v1.0.2: User PII 字段(email/phone)已加密
    assert is_sensitive("users", "email") is True
    assert is_sensitive("users", "phone") is True
    # 非敏感字段
    assert is_sensitive("sites", "name") is False
    assert is_sensitive("sites", "pollution_type") is False
    assert is_sensitive("users", "username") is False


def test_backup_create_and_verify(fresh_db):
    """备份创建 + 恢复演练(GPT 9.2)。"""
    from app.services.backup_service import create_backup, verify_backup
    result = create_backup("test")
    assert "sha256" in result
    assert result["size_bytes"] > 0
    # 恢复演练
    ver = verify_backup(result["path"])
    assert ver["valid"] is True, "备份应可恢复"
    assert ver["n_tables"] > 0, "备份应包含表"


def test_backup_list(fresh_db):
    """备份列表。"""
    from app.services.backup_service import create_backup, list_backups
    create_backup("list_test_1")
    backups = list_backups()
    assert len(backups) >= 1
    assert "filename" in backups[0]


def test_restore_requires_confirm(fresh_db):
    """恢复需要二次确认(防误操作)。"""
    from app.services.backup_service import create_backup, restore_backup
    result = create_backup("restore_test")
    # 不确认 → 应报错
    with pytest.raises(ValueError, match="confirm"):
        restore_backup(result["path"], confirm=False)
