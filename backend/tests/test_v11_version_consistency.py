"""v1.1: 所有版本声明必须与仓库根 VERSION 一致(缺陷 D-11)。"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_all_version_declarations_match_single_source():
    v = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    assert re.fullmatch(r"\d+\.\d+\.\d+", v)
    from app.version import __version__
    assert __version__ == v
    assert "version=__version__" in (ROOT / "backend/app/main.py").read_text(encoding="utf-8")
    assert json.loads((ROOT / "frontend/package.json").read_text(encoding="utf-8"))["version"] == v
    iss = (ROOT / "packaging/srs_setup.iss").read_text(encoding="utf-8")
    assert f'#define MyAppVersion "{v}"' in iss and f"SRS-Setup-{v}-Windows-x64" in iss
    four = v + ".0"
    tup = "(" + ", ".join(v.split(".") + ["0"]) + ")"
    for rel in ("packaging/version_info.py", "packaging/srs.spec", "packaging/inject_version.py"):
        src = (ROOT / rel).read_text(encoding="utf-8")
        assert four in src, rel
        assert not re.search(r"1\.0\.[0-9]\.0", src), rel
        if "filevers" in src:
            assert f"filevers={tup}" in src.replace(" ", "").replace(",", ", ").replace("filevers=", "filevers=") or \
                f"filevers={tup.replace(' ', '')}" in src.replace(" ", ""), rel
