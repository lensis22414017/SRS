#!/bin/bash
# SRS v0.2 P0-6: 数据库 + 文件存储备份脚本
# 用法: bash scripts/backup_db.sh
# 输出: backups/srs_backup_YYYYMMDD_HHMMSS.zip

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BACKUP_DIR="$PROJECT_DIR/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_NAME="srs_backup_${TIMESTAMP}"
BACKUP_PATH="$BACKUP_DIR/$BACKUP_NAME"

mkdir -p "$BACKUP_DIR"

echo "=== SRS 系统备份 $TIMESTAMP ==="

# 1. 备份 SQLite 数据库
DB_PATH="${SRS_DB_PATH:-$PROJECT_DIR/backend/srs_dev.db}"
if [ -f "$DB_PATH" ]; then
    cp "$DB_PATH" "$BACKUP_PATH.db"
    echo "[OK] 数据库备份: $(wc -c < "$BACKUP_PATH.db") bytes"
else
    echo "[WARN] 数据库文件不存在: $DB_PATH"
fi

# 2. 备份文件存储目录
STORAGE_DIR="${SRS_STORAGE_DIR:-$PROJECT_DIR/backend/storage}"
if [ -d "$STORAGE_DIR" ]; then
    cp -r "$STORAGE_DIR" "$BACKUP_PATH.storage"
    echo "[OK] 文件存储备份: $(find "$BACKUP_PATH.storage" -type f | wc -l) 个文件"
else
    echo "[WARN] 存储目录不存在: $STORAGE_DIR"
fi

# 3. 打包
cd "$BACKUP_DIR"
zip -rq "${BACKUP_NAME}.zip" "$BACKUP_NAME.db" "$BACKUP_NAME.storage" 2>/dev/null || tar czf "${BACKUP_NAME}.tar.gz" "$BACKUP_NAME.db" "$BACKUP_NAME.storage"
ARCHIVE="$BACKUP_DIR/${BACKUP_NAME}.zip"
[ -f "$ARCHIVE" ] || ARCHIVE="$BACKUP_DIR/${BACKUP_NAME}.tar.gz"
echo "[OK] 打包完成: $ARCHIVE"

# 4. 清理临时文件
rm -rf "$BACKUP_PATH.db" "$BACKUP_PATH.storage"

# 5. 保留最近 10 个备份
ls -t "$BACKUP_DIR"/srs_backup_* 2>/dev/null | tail -n +11 | xargs rm -f 2>/dev/null || true

echo "=== 备份完成 ==="
echo "备份文件: $ARCHIVE"
