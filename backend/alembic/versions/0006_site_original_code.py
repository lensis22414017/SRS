"""保存原始场地编号并使用无数字展示编号。

Revision ID: 0006_site_original_code
Revises: 0005_round9
Create Date: 2026-07-20
"""
from alembic import op
import sqlalchemy as sa
import re


revision = "0006_site_original_code"
down_revision = "0005_round9"
branch_labels = None
depends_on = None


def _to_base26(n: int) -> str:
    n = max(int(n), 1)
    chars = []
    while n:
        n, rem = divmod(n - 1, 26)
        chars.append(chr(ord("A") + rem))
    return "".join(reversed(chars))


def _migrate_existing_codes() -> None:
    bind = op.get_bind()
    rows = bind.execute(sa.text(
        "SELECT id, site_code, original_site_code FROM sites ORDER BY id"
    )).mappings().all()
    invalid = []
    used = set()
    for row in rows:
        code = str(row["site_code"] or "").strip()
        safe = bool(re.fullmatch(r"[A-Za-z]+(?:-[A-Za-z]+)*", code))
        if safe and not code.upper().startswith("AUTO"):
            used.add(code.upper())
        else:
            invalid.append((int(row["id"]), code, row["original_site_code"]))

    # 先移到不会与正式编号冲突的纯字母临时值，避开 UNIQUE(site_code) 的换位冲突。
    for site_id, _, _ in invalid:
        temporary = f"TMP-{_to_base26(site_id)}-{_to_base26(site_id + 1000000)}"
        bind.execute(
            sa.text("UPDATE sites SET site_code=:code WHERE id=:site_id"),
            {"code": temporary, "site_id": site_id},
        )

    for site_id, old_code, original_code in invalid:
        candidate = f"SRS-{_to_base26(site_id)}"
        suffix = 1
        while candidate in used:
            candidate = f"SRS-{_to_base26(site_id)}-{_to_base26(suffix)}"
            suffix += 1
        used.add(candidate)
        bind.execute(
            sa.text(
                "UPDATE sites SET site_code=:new_code, original_site_code=:original "
                "WHERE id=:site_id"
            ),
            {
                "new_code": candidate,
                "original": original_code or old_code or None,
                "site_id": site_id,
            },
        )


def upgrade():
    inspector = sa.inspect(op.get_bind())
    columns = {c["name"] for c in inspector.get_columns("sites")}
    if "original_site_code" not in columns:
        with op.batch_alter_table("sites") as batch:
            batch.add_column(sa.Column("original_site_code", sa.String(length=120), nullable=True))
    indexes = {i["name"] for i in sa.inspect(op.get_bind()).get_indexes("sites")}
    if "ix_sites_original_site_code" not in indexes:
        with op.batch_alter_table("sites") as batch:
            batch.create_index("ix_sites_original_site_code", ["original_site_code"], unique=False)
    _migrate_existing_codes()


def downgrade():
    indexes = {i["name"] for i in sa.inspect(op.get_bind()).get_indexes("sites")}
    if "ix_sites_original_site_code" in indexes:
        with op.batch_alter_table("sites") as batch:
            batch.drop_index("ix_sites_original_site_code")
    columns = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("sites")}
    if "original_site_code" in columns:
        with op.batch_alter_table("sites") as batch:
            batch.drop_column("original_site_code")
