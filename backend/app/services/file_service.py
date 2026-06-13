"""本地文件对象存储 (MVP 替代 MinIO)。"""
from __future__ import annotations

import hashlib
import os
import shutil
import uuid

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import FileObject


def save_bytes(db: Session, data: bytes, original_name: str,
               content_type: str | None = None,
               organization_id: int | None = None) -> FileObject:
    settings = get_settings()
    base = os.path.abspath(settings.file_storage_dir)
    os.makedirs(base, exist_ok=True)
    key = f"{uuid.uuid4().hex}_{original_name}"
    path = os.path.join(base, key)
    with open(path, "wb") as f:
        f.write(data)
    sha = hashlib.sha256(data).hexdigest()
    obj = FileObject(storage_key=key, original_name=original_name,
                     content_type=content_type, size_bytes=len(data),
                     sha256=sha, organization_id=organization_id)
    db.add(obj)
    db.flush()
    return obj


def save_upload(db: Session, file_obj, original_name: str,
                content_type: str | None = None,
                organization_id: int | None = None) -> FileObject:
    data = file_obj.read()
    return save_bytes(db, data, original_name, content_type, organization_id)


def abs_path(storage_key: str) -> str:
    return os.path.join(os.path.abspath(get_settings().file_storage_dir), storage_key)
