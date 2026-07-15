import json

path = r"G:\文献整理_最终\2024_Xie X et al_EcotoxicolEnvironSaf_10.1016-j.ecoenv.2024.116965\2024_Xie X et al_EcotoxicolEnvironSaf_10.1016-j.ecoenv.2024.116965\auto\2024_Xie X et al_EcotoxicolEnvironSaf_10.1016-j.ecoenv.2024.116965_middle.json"

with open(path, "r", encoding="utf-8") as f:
    data = json.load(f)

outpath = r"C:\Users\曾鸿\Desktop\SRS\outputs\literature_mining\_scripts\tmp_full.txt"

pdf_info = data["pdf_info"]
with open(outpath, "w", encoding="utf-8") as f:
    f.write(f"pdf_info list of {len(pdf_info)}\n")
    for i, page in enumerate(pdf_info):
        f.write(f"\n=== Page {i} ===\n")
        if isinstance(page, dict):
            keys = list(page.keys())
            f.write(f"Keys: {keys}\n")
            for k in keys:
                v = page[k]
                if isinstance(v, list):
                    f.write(f"  {k}: list of {len(v)}\n")
                    for j, item in enumerate(v):
                        if isinstance(item, dict):
                            k2 = list(item.keys())
                            tp = item.get("type", "N/A")
                            f.write(f"    [{j}] type={tp} keys={k2}\n")
                            if j > 3:
                                f.write(f"    ... truncated\n")
                                break
                elif isinstance(v, dict):
                    f.write(f"  {k}: dict keys={list(v.keys())}\n")
                elif isinstance(v, str):
                    f.write(f"  {k}: str len={len(v)}\n")
        if i > 5:
            f.write("\n... truncated pages\n")
            break

print("Done")
