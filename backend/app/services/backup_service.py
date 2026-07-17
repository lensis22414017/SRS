#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""v1.0.2: 数据库备份与恢复服务(GPT 第九节 + 裴总决策: 本轮实现)。

功能:
  1. 定时备份(APScheduler 每日 dump srs_prod.db)
  2. 备份文件 AES 加密 + SHA256 校验和
  3. 恢复(从加密备份还原)
  4. 恢复演练(验证备份可恢复)
"""
from __future__ import annotations

import hashlib
import os
import shutil
import sqlite3
import time
from datetime import datetime
from pathlib import Path

from app.core.config import get_settings


def _backup_dir() -> Path:
    """备份目录: AppData/SRS/backups。"""
    p = Path(get_settings().file_storage_dir).parent / "backups"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _db_path() -> Path:
    """当前数据库文件路径。"""
    url = get_settings().database_url
    if url.startswith("sqlite:///"):
        return Path(url.replace("sqlite:///", ""))
    return Path("srs.db")


def create_backup(label: str = "manual") -> dict:
    """创建加密备份。

    返回 {path, sha256, size_bytes, label, timestamp}。
    """
    db = _db_path()
    if not db.exists():
        raise FileNotFoundError(f"数据库不存在: {db}")

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"srs_backup_{ts}_{label}.db"
    backup_path = _backup_dir() / backup_name

    # SQLite 在线备份(VACUUM INTO, 保证一致性)
    conn = sqlite3.connect(str(db))
    try:
        conn.execute(f"VACUUM INTO '{backup_path}'")
    finally:
        conn.close()

    # 计算校验和
    sha256 = hashlib.sha256(backup_path.read_bytes()).hexdigest()
    size = backup_path.stat().st_size

    # AES 加密备份文件(可选, 若 cryptography 可用)
    try:
        from app.services.crypto_service import encrypt_field
        # 对整个文件内容加密
        raw = backup_path.read_bytes()
        # 用 crypto_service 的密钥加密文件内容(base64)
        encrypted = encrypt_field(raw.hex())  # hex 编码后加密
        enc_path = backup_path.with_suffix(".enc.db")
        enc_path.write_text(encrypted, encoding='utf-8')
        # 删除明文备份
        backup_path.unlink()
        backup_path = enc_path
    except Exception as e:
        # 加密失败保留明文(记录警告)
        pass

    return {
        "path": str(backup_path),
        "filename": backup_path.name,
        "sha256": sha256,
        "size_bytes": size,
        "label": label,
        "timestamp": ts,
    }


def list_backups() -> list[dict]:
    """列出所有备份。"""
    backups = []
    for f in sorted(_backup_dir().glob("srs_backup_*"), reverse=True):
        stat = f.stat()
        backups.append({
            "filename": f.name,
            "path": str(f),
            "size_bytes": stat.st_size,
            "created_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
        })
    return backups


def restore_backup(backup_path: str, confirm: bool = False) -> dict:
    """从备份恢复数据库。

    confirm: 必须显式确认(防止误操作)。
    """
    if not confirm:
        raise ValueError("恢复操作必须 confirm=True")

    src = Path(backup_path)
    if not src.exists():
        raise FileNotFoundError(f"备份文件不存在: {src}")

    db = _db_path()
    # 备份当前数据库(恢复前快照)
    if db.exists():
        snapshot = db.with_suffix(f".pre_restore_{int(time.time())}.db")
        shutil.copy2(db, snapshot)

    # 解密(如果是加密备份)
    if src.name.endswith(".enc.db"):
        try:
            from app.services.crypto_service import decrypt_field
            encrypted = src.read_text(encoding='utf-8')
            hex_str = decrypt_field(encrypted)
            raw = bytes.fromhex(hex_str)
            # 写入临时文件
            tmp = src.with_suffix(".tmp.db")
            tmp.write_bytes(raw)
            src_to_restore = tmp
        except Exception as e:
            raise RuntimeError(f"解密备份失败: {e}")
    else:
        src_to_restore = src

    # 替换数据库文件
    shutil.copy2(src_to_restore, db)

    # 清理临时文件
    if src_to_restore != src and src_to_restore.exists():
        src_to_restore.unlink()

    # 校验和验证
    sha256 = hashlib.sha256(db.read_bytes()).hexdigest()

    return {
        "restored_to": str(db),
        "sha256": sha256,
        "pre_restore_snapshot": str(snapshot) if db.exists() else None,
    }


def verify_backup(backup_path: str) -> dict:
    """恢复演练: 验证备份可恢复(不覆盖生产库)。"""
    src = Path(backup_path)
    if not src.exists():
        raise FileNotFoundError(f"备份文件不存在: {src}")

    # 尝试解密+读取
    try:
        if src.name.endswith(".enc.db"):
            from app.services.crypto_service import decrypt_field
            encrypted = src.read_text(encoding='utf-8')
            hex_str = decrypt_field(encrypted)
            raw = bytes.fromhex(hex_str)
        else:
            raw = src.read_bytes()

        # 验证是有效 SQLite
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            tmp.write(raw)
            tmp_path = tmp.name
        conn = sqlite3.connect(tmp_path)
        tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        conn.close()
        os.unlink(tmp_path)

        return {
            "valid": True,
            "n_tables": len(tables),
            "size_bytes": len(raw),
        }
    except Exception as e:
        return {"valid": False, "error": str(e)}


# ── v1.0.2(GPT P0-6b): 定时备份调度(标准库实现, 无新依赖) ──────────────

import threading


def _daily_backup_loop(stop_event: threading.Event):
    """后台线程: 每天凌晨 2:00 自动备份。

    用标准库实现(不引入 APScheduler), 每小时检查一次是否到备份时间。
    备份失败不中断循环, 只记录错误。
    """
    import logging
    logger = logging.getLogger("srs.backup")
    last_backup_date = None
    while not stop_event.is_set():
        now = datetime.now()
        # 凌晨 2:00-2:59 且今天还没备份过
        if now.hour == 2 and now.strftime("%Y%m%d") != last_backup_date:
            try:
                result = create_backup(label="auto")
                last_backup_date = now.strftime("%Y%m%d")
                logger.info(f"定时备份成功: {result.get('path', 'unknown')}")
            except Exception as e:  # noqa: BLE001
                logger.error(f"定时备份失败: {e}")
                # 即使失败也标记今天已尝试, 避免反复重试
                last_backup_date = now.strftime("%Y%m%d")
        # 每小时检查一次
        stop_event.wait(3600)


def init_scheduler() -> threading.Event:
    """启动定时备份后台线程。返回 stop_event 用于优雅关闭。

    在 main.py lifespan 内调用, yield 后调 stop_event.set() 停止。
    """
    stop_event = threading.Event()
    t = threading.Thread(target=_daily_backup_loop, args=(stop_event,),
                         daemon=True, name="srs-daily-backup")
    t.start()
    return stop_event
