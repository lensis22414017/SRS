"""本地文件对象存储 (MVP 替代 MinIO)。"""
from __future__ import annotations

import hashlib
import os
import re
import uuid

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import FileObject

# v0.2 P0-2: 文件安全 — 默认最大 50MB, 可配置
MAX_UPLOAD_SIZE_BYTES = 50 * 1024 * 1024

# v0.2 P0-2: 合法 MIME 白名单
ALLOWED_MIME_PREFIXES = (
    "application/pdf", "application/msword",
    "application/vnd.openxmlformats-officedocument",
    "application/vnd.ms-excel",
    "application/octet-stream",      # 通用二进制(允许未知类型)
    "application/zip",               # ZIP 压缩包
    "image/", "text/csv", "text/plain",
)


def _sanitize_filename(name: str) -> str:
    """移除路径遍历字符和危险序列, 保留安全文件名。"""
    # 去掉路径分隔符
    safe = name.replace("\\", "_").replace("/", "_")
    # 去掉连续的点和空字符
    safe = re.sub(r'\.{2,}', '_', safe)
    safe = re.sub(r'[\x00-\x1f]', '', safe)
    # 去掉首尾空格和点
    safe = safe.strip(" .")
    return safe or "unnamed_file"


def _validate_upload(data: bytes, original_name: str, content_type: str | None):
    """校验上传文件大小和 MIME 类型。"""
    if len(data) > MAX_UPLOAD_SIZE_BYTES:
        raise ValueError(
            f"文件大小 {len(data) / 1024 / 1024:.1f}MB 超过上限 "
            f"{MAX_UPLOAD_SIZE_BYTES / 1024 / 1024:.0f}MB"
        )
    if content_type and not any(content_type.startswith(p) for p in ALLOWED_MIME_PREFIXES):
        raise ValueError(f"不支持的文件类型: {content_type}")


def save_bytes(db: Session, data: bytes, original_name: str,
               content_type: str | None = None,
               organization_id: int | None = None) -> FileObject:
    settings = get_settings()
    # v0.2 P0-2: 文件安全校验
    safe_name = _sanitize_filename(original_name)
    _validate_upload(data, safe_name, content_type)

    base = os.path.abspath(settings.file_storage_dir)
    os.makedirs(base, exist_ok=True)
    key = f"{uuid.uuid4().hex}_{safe_name}"
    path = os.path.join(base, key)
    # 二次确认路径在 base 内 (防路径遍历)
    if not os.path.abspath(path).startswith(base):
        raise ValueError(f"非法文件路径: {path}")
    with open(path, "wb") as f:
        f.write(data)
    sha = hashlib.sha256(data).hexdigest()
    obj = FileObject(storage_key=key, original_name=safe_name,
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
