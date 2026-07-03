from __future__ import annotations
import argparse, json, zipfile
from pathlib import Path

def docx_images(p: Path) -> int:
    with zipfile.ZipFile(p) as z:
        return len([n for n in z.namelist() if n.startswith("word/media/")])

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="+"); ap.add_argument("--min-images", type=int, default=1)
    args = ap.parse_args()
    rows, ok = [], True
    for s in args.paths:
        p = Path(s)
        if p.suffix.lower() == ".docx":
            n = docx_images(p)
        elif p.suffix.lower() == ".pdf":
            # lightweight check: PDF binary should contain image XObject marker; pypdf can replace this if installed
            raw = p.read_bytes()
            n = raw.count(b"/Subtype /Image") + raw.count(b"/Image")
        else:
            continue
        passed = n >= args.min_images
        ok = ok and passed
        rows.append({"file": str(p), "image_count_hint": n, "passed": passed})
    print(json.dumps({"passed": ok, "results": rows}, ensure_ascii=False, indent=2))
    if not ok: raise SystemExit(2)
if __name__ == "__main__": main()
