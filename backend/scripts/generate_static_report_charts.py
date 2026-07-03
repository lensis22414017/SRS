from __future__ import annotations
import argparse, json
from pathlib import Path
import matplotlib.pyplot as plt
import pandas as pd

def ensure(out: Path): out.mkdir(parents=True, exist_ok=True)

def save_site_map(payload, out: Path):
    pts = pd.DataFrame(payload.get("points", []))
    if pts.empty: raise ValueError("site_map points is empty")
    lon = "lon" if "lon" in pts.columns else "longitude"
    lat = "lat" if "lat" in pts.columns else "latitude"
    fig, ax = plt.subplots(figsize=(7.2,5.2), dpi=160)
    if "risk_level" in pts.columns:
        for lvl, g in pts.groupby("risk_level"):
            ax.scatter(g[lon], g[lat], s=50, label=str(lvl), alpha=.85)
        ax.legend(title="风险等级")
    else:
        ax.scatter(pts[lon], pts[lat], s=50, alpha=.85)
    ax.set_title("场地采样点分布与风险分级")
    ax.set_xlabel("经度"); ax.set_ylabel("纬度"); ax.grid(alpha=.25); ax.ticklabel_format(useOffset=False)
    fig.tight_layout(); fp = out/"site_map_static.png"; fig.savefig(fp, bbox_inches="tight"); plt.close(fig); return fp

def save_topn(payload, out: Path):
    df = pd.DataFrame(payload.get("factors", []))
    if df.empty: raise ValueError("barrier factors is empty")
    name = "factor_name" if "factor_name" in df.columns else "factor"
    score = "key_score" if "key_score" in df.columns else "score"
    df = df.sort_values(score, ascending=True).tail(10)
    fig, ax = plt.subplots(figsize=(8,4.8), dpi=160)
    ax.barh(df[name].astype(str), df[score].astype(float))
    ax.set_title("污染场地关键障碍因子 Top-N"); ax.set_xlabel("综合得分"); ax.grid(axis="x", alpha=.25)
    fig.tight_layout(); fp = out/"barrier_topn.png"; fig.savefig(fp, bbox_inches="tight"); plt.close(fig); return fp

def save_ssui(payload, out: Path):
    safety, economy, ssui = float(payload.get("safety_score",0)), float(payload.get("economic_score",0)), float(payload.get("ssui",0))
    fig, ax = plt.subplots(figsize=(5.2,4.8), dpi=160)
    ax.scatter([safety], [economy], s=260+ssui*460)
    ax.axvline(.6, linestyle="--", linewidth=1); ax.axhline(.6, linestyle="--", linewidth=1)
    ax.set_xlim(0,1); ax.set_ylim(0,1); ax.set_xlabel("安全性"); ax.set_ylabel("经济性")
    ax.set_title(f"SSUI 安全性-经济性矩阵：{ssui:.3f}"); ax.grid(alpha=.25)
    fig.tight_layout(); fp = out/"ssui_safety_economy.png"; fig.savefig(fp, bbox_inches="tight"); plt.close(fig); return fp

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True); ap.add_argument("--out", required=True)
    args = ap.parse_args()
    payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    out = Path(args.out); ensure(out)
    made = []
    if "site_map" in payload: made.append(str(save_site_map(payload["site_map"], out)))
    if "barrier_topn" in payload: made.append(str(save_topn(payload["barrier_topn"], out)))
    if "ssui" in payload: made.append(str(save_ssui(payload["ssui"], out)))
    (out/"manifest.json").write_text(json.dumps({"image_count":len(made),"created":made},ensure_ascii=False,indent=2), encoding="utf-8")
    print(json.dumps({"image_count":len(made),"created":made},ensure_ascii=False,indent=2))
if __name__ == "__main__": main()
