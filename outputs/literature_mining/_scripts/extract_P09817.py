#!/usr/bin/env python3
"""
P09817: Ren J et al. - Characterization of Tibetan soil as a source or sink
of atmospheric persistent organic pollutants: Seasonal shift and impact of
global warming.

Data source: Table S8 (Soil concentrations, pg/g dw) - Parts I, II, III
Lulang, Nam Co, Ngari sites. OCPs (HCHs, DDTs, HCB) + PCBs.
No HM data, no PAH data.

BDL values treated as 0 for sum calculations (conservative, noted in extract_notes).
"""

import csv
import os
import json

PAPER_ID = "P09817"
OUTPUT_DIR = r"C:\Users\曾鸿\Desktop\SRS\outputs\literature_mining\manual_extract\op_only"
OUTPUT_PATH = os.path.join(OUTPUT_DIR, f"{PAPER_ID}.csv")

os.makedirs(OUTPUT_DIR, exist_ok=True)

# ---------------------------------------------------------------------------
# Raw data from Table S8 (all values in pg/g dw, which equals ng/g numerically)
# BDL -> 0
# ---------------------------------------------------------------------------

def compute(s):
    """Compute SumHCH, SumDDT, SumPCB for one sample dict."""
    sum_hch = s["a"] + s["b"] + s["g"] + s["d"]
    sum_ddt = s["opDDE"] + s["ppDDE"] + s["opDDT"] + s["ppDDT"]
    pcb_parts = [s[v] for v in ("PCB28","PCB52","PCB101","PCB153","PCB138","PCB180")]
    pcb_sum = sum(v for v in pcb_parts if v is not None)
    bdl_note = []
    for lbl, val in [("a-HCH",s["a"]),("b-HCH",s["b"]),("g-HCH",s["g"]),("d-HCH",s["d"]),
                      ("HCB",s["HCB"]),("o,p'-DDE",s["opDDE"]),("p,p'-DDE",s["ppDDE"]),
                      ("o,p'-DDT",s["opDDT"]),("p,p'-DDT",s["ppDDT"])]:
        if val == 0:
            bdl_note.append(f"{lbl}=BDL")
    for lbl, val in [("PCB28",s["PCB28"]),("PCB52",s["PCB52"]),("PCB101",s["PCB101"]),
                      ("PCB153",s["PCB153"]),("PCB138",s["PCB138"]),("PCB180",s["PCB180"])]:
        if val is None:
            bdl_note.append(f"{lbl}=N/A(PDF parse corrupt)")
        elif val == 0:
            bdl_note.append(f"{lbl}=BDL")
    return sum_hch, sum_ddt, pcb_sum, "; ".join(bdl_note)

# ==================== LULANG ====================
lulang = [
    # Summer
    {"id":"2013.08.21A","site":"Lulang","season":"summer","a":230,"b":403,"g":0,"d":0,
     "HCB":875,"opDDE":50,"ppDDE":1176,"opDDT":693,"ppDDT":1323,
     "PCB28":65,"PCB52":16,"PCB101":7,"PCB153":22,"PCB138":19,"PCB180":0},
    {"id":"2013.08.21_B","site":"Lulang","season":"summer","a":116,"b":148,"g":9,"d":13,
     "HCB":936,"opDDE":47,"ppDDE":557,"opDDT":480,"ppDDT":702,
     "PCB28":54,"PCB52":15,"PCB101":6,"PCB153":10,"PCB138":11,"PCB180":1},
    {"id":"2013.08.26_A","site":"Lulang","season":"summer","a":132,"b":325,"g":0,"d":0,
     "HCB":520,"opDDE":20,"ppDDE":951,"opDDT":687,"ppDDT":915,
     "PCB28":44,"PCB52":8,"PCB101":9,"PCB153":16,"PCB138":18,"PCB180":0},
    {"id":"2013.08.26_B","site":"Lulang","season":"summer","a":137,"b":131,"g":10,"d":23,
     "HCB":605,"opDDE":78,"ppDDE":714,"opDDT":571,"ppDDT":898,
     "PCB28":47,"PCB52":13,"PCB101":8,"PCB153":14,"PCB138":16,"PCB180":0},
    # Winter
    {"id":"2015.01.07_A","site":"Lulang","season":"winter","a":101,"b":96,"g":0,"d":0,
     "HCB":764,"opDDE":28,"ppDDE":213,"opDDT":151,"ppDDT":231,
     "PCB28":52,"PCB52":10,"PCB101":4,"PCB153":4,"PCB138":6,"PCB180":0},
    {"id":"2015.01.07_B","site":"Lulang","season":"winter","a":103,"b":318,"g":27,"d":0,
     "HCB":463,"opDDE":45,"ppDDE":1268,"opDDT":1522,"ppDDT":2485,
     "PCB28":21,"PCB52":9,"PCB101":23,"PCB153":16,"PCB138":35,"PCB180":4},
    {"id":"2015.01.13_A","site":"Lulang","season":"winter","a":252,"b":416,"g":38,"d":79,
     "HCB":2813,"opDDE":68,"ppDDE":608,"opDDT":378,"ppDDT":691,
     "PCB28":126,"PCB52":19,"PCB101":12,"PCB153":14,"PCB138":27,"PCB180":0},
    {"id":"2015.01.13_B","site":"Lulang","season":"winter","a":85,"b":266,"g":0,"d":11,
     "HCB":1985,"opDDE":42,"ppDDE":540,"opDDT":367,"ppDDT":586,
     "PCB28":0,"PCB52":7,"PCB101":12,"PCB153":19,"PCB138":26,"PCB180":1},
    {"id":"2015.01.18_A","site":"Lulang","season":"winter","a":195,"b":341,"g":24,"d":32,
     "HCB":1720,"opDDE":77,"ppDDE":854,"opDDT":529,"ppDDT":982,
     "PCB28":147,"PCB52":32,"PCB101":9,"PCB153":19,"PCB138":32,"PCB180":0},
    {"id":"2015.01.18_B","site":"Lulang","season":"winter","a":157,"b":132,"g":23,"d":14,
     "HCB":1596,"opDDE":30,"ppDDE":485,"opDDT":385,"ppDDT":252,
     "PCB28":35,"PCB52":7,"PCB101":7,"PCB153":13,"PCB138":16,"PCB180":0},
    # 2015.01.23_A: label lost in PDF parse, reconstructed from row data
    {"id":"2015.01.23_A","site":"Lulang","season":"winter","a":85,"b":151,"g":28,"d":0,
     "HCB":498,"opDDE":20,"ppDDE":336,"opDDT":329,"ppDDT":706,
     "PCB28":None,"PCB52":None,"PCB101":8,"PCB153":6,"PCB138":9,"PCB180":None},
    # 2015.01.23_B: merged label "2015.01.23 A 2015.01.23 B", PCB28/52 split values
    {"id":"2015.01.23_B","site":"Lulang","season":"winter","a":91,"b":156,"g":27,"d":0,
     "HCB":1021,"opDDE":17,"ppDDE":220,"opDDT":320,"ppDDT":517,
     "PCB28":24,"PCB52":5,"PCB101":9,"PCB153":5,"PCB138":8,"PCB180":2},
]

# ==================== NAM CO ====================
namco = [
    {"id":"2013.08.03_A","site":"Nam Co","season":"summer","a":6,"b":35,"g":6,"d":2,
     "HCB":78,"opDDE":49,"ppDDE":329,"opDDT":67,"ppDDT":391,
     "PCB28":11,"PCB52":4,"PCB101":12,"PCB153":3,"PCB138":13,"PCB180":0},
    {"id":"2013.08.03_B","site":"Nam Co","season":"summer","a":0,"b":10,"g":0,"d":2,
     "HCB":0,"opDDE":0,"ppDDE":29,"opDDT":16,"ppDDT":159,
     "PCB28":4,"PCB52":2,"PCB101":3,"PCB153":1,"PCB138":2,"PCB180":0},
    {"id":"2012.12.03_A","site":"Nam Co","season":"winter","a":5,"b":23,"g":23,"d":0,
     "HCB":367,"opDDE":11,"ppDDE":72,"opDDT":16,"ppDDT":1125,
     "PCB28":22,"PCB52":1,"PCB101":7,"PCB153":2,"PCB138":2,"PCB180":0},
    {"id":"2012.12.03_B","site":"Nam Co","season":"winter","a":0,"b":0,"g":0,"d":0,
     "HCB":0,"opDDE":8,"ppDDE":16,"opDDT":26,"ppDDT":35,
     "PCB28":1,"PCB52":0,"PCB101":4,"PCB153":0,"PCB138":1,"PCB180":1},
    {"id":"2012.12.06_A","site":"Nam Co","season":"winter","a":6,"b":9,"g":10,"d":15,
     "HCB":336,"opDDE":21,"ppDDE":59,"opDDT":20,"ppDDT":160,
     "PCB28":11,"PCB52":1,"PCB101":9,"PCB153":1,"PCB138":2,"PCB180":0},
    {"id":"2012.12.06_B","site":"Nam Co","season":"winter","a":11,"b":0,"g":16,"d":29,
     "HCB":115,"opDDE":35,"ppDDE":153,"opDDT":164,"ppDDT":338,
     "PCB28":10,"PCB52":0,"PCB101":14,"PCB153":0,"PCB138":6,"PCB180":1},
    {"id":"2012.12.12_A","site":"Nam Co","season":"winter","a":7,"b":21,"g":14,"d":0,
     "HCB":350,"opDDE":52,"ppDDE":113,"opDDT":45,"ppDDT":235,
     "PCB28":14,"PCB52":2,"PCB101":8,"PCB153":1,"PCB138":4,"PCB180":0},
    {"id":"2012.12.12_B","site":"Nam Co","season":"winter","a":0,"b":0,"g":0,"d":6,
     "HCB":106,"opDDE":31,"ppDDE":65,"opDDT":18,"ppDDT":22,
     "PCB28":7,"PCB52":0,"PCB101":8,"PCB153":0,"PCB138":0,"PCB180":1},
]

# ==================== NGARI ====================
ngari = [
    # Summer
    {"id":"2014.06.09_A","site":"Ngari","season":"summer","a":0,"b":0,"g":4,"d":4,
     "HCB":78,"opDDE":0,"ppDDE":18,"opDDT":0,"ppDDT":1826,
     "PCB28":33,"PCB52":15,"PCB101":5,"PCB153":0,"PCB138":1,"PCB180":0},
    {"id":"2014.06.09_B","site":"Ngari","season":"summer","a":0,"b":0,"g":7,"d":6,
     "HCB":121,"opDDE":0,"ppDDE":18,"opDDT":0,"ppDDT":653,
     "PCB28":35,"PCB52":15,"PCB101":4,"PCB153":0,"PCB138":0,"PCB180":0},
    {"id":"2014.06.14_A","site":"Ngari","season":"summer","a":0,"b":18,"g":3,"d":0,
     "HCB":80,"opDDE":0,"ppDDE":31,"opDDT":0,"ppDDT":2938,
     "PCB28":18,"PCB52":10,"PCB101":4,"PCB153":0,"PCB138":1,"PCB180":0},
    {"id":"2014.06.14_B","site":"Ngari","season":"summer","a":0,"b":0,"g":6,"d":4,
     "HCB":144,"opDDE":16,"ppDDE":39,"opDDT":14,"ppDDT":1131,
     "PCB28":48,"PCB52":26,"PCB101":6,"PCB153":1,"PCB138":2,"PCB180":0},
    {"id":"2014.06.19_A","site":"Ngari","season":"summer","a":13,"b":22,"g":17,"d":11,
     "HCB":258,"opDDE":20,"ppDDE":60,"opDDT":39,"ppDDT":2824,
     "PCB28":73,"PCB52":36,"PCB101":8,"PCB153":0,"PCB138":4,"PCB180":0},
    {"id":"2014.06.19_B","site":"Ngari","season":"summer","a":4,"b":9,"g":5,"d":4,
     "HCB":174,"opDDE":13,"ppDDE":31,"opDDT":17,"ppDDT":1410,
     "PCB28":32,"PCB52":12,"PCB101":1,"PCB153":0,"PCB138":1,"PCB180":0},
    {"id":"2014.06.24_A","site":"Ngari","season":"summer","a":8,"b":17,"g":4,"d":6,
     "HCB":209,"opDDE":11,"ppDDE":37,"opDDT":9,"ppDDT":727,
     "PCB28":21,"PCB52":9,"PCB101":3,"PCB153":0,"PCB138":1,"PCB180":0},
    {"id":"2014.06.24_B","site":"Ngari","season":"summer","a":6,"b":13,"g":1,"d":0,
     "HCB":100,"opDDE":0,"ppDDE":28,"opDDT":0,"ppDDT":1373,
     "PCB28":15,"PCB52":5,"PCB101":2,"PCB153":0,"PCB138":1,"PCB180":0},
    # Winter
    {"id":"2014.10.07_A","site":"Ngari","season":"winter","a":0,"b":13,"g":10,"d":0,
     "HCB":141,"opDDE":9,"ppDDE":21,"opDDT":0,"ppDDT":857,
     "PCB28":30,"PCB52":5,"PCB101":2,"PCB153":0,"PCB138":1,"PCB180":0},
    {"id":"2014.10.07_B","site":"Ngari","season":"winter","a":10,"b":9,"g":7,"d":4,
     "HCB":94,"opDDE":8,"ppDDE":28,"opDDT":11,"ppDDT":1239,
     "PCB28":9,"PCB52":12,"PCB101":3,"PCB153":0,"PCB138":1,"PCB180":0},
    {"id":"2014.10.12_A","site":"Ngari","season":"winter","a":0,"b":13,"g":5,"d":6,
     "HCB":116,"opDDE":8,"ppDDE":20,"opDDT":0,"ppDDT":877,
     "PCB28":103,"PCB52":10,"PCB101":3,"PCB153":0,"PCB138":0,"PCB180":0},
    {"id":"2014.10.12_B","site":"Ngari","season":"winter","a":0,"b":17,"g":2,"d":0,
     "HCB":60,"opDDE":0,"ppDDE":14,"opDDT":0,"ppDDT":1741,
     "PCB28":43,"PCB52":4,"PCB101":1,"PCB153":0,"PCB138":0,"PCB180":0},
    {"id":"2014.10.17_A","site":"Ngari","season":"winter","a":0,"b":14,"g":0,"d":5,
     "HCB":51,"opDDE":0,"ppDDE":14,"opDDT":0,"ppDDT":1380,
     "PCB28":17,"PCB52":3,"PCB101":1,"PCB153":0,"PCB138":0,"PCB180":0},
    {"id":"2014.10.17_B","site":"Ngari","season":"winter","a":11,"b":18,"g":6,"d":0,
     "HCB":127,"opDDE":0,"ppDDE":21,"opDDT":0,"ppDDT":1146,
     "PCB28":30,"PCB52":7,"PCB101":2,"PCB153":0,"PCB138":0,"PCB180":0},
    {"id":"2014.10.22_A","site":"Ngari","season":"winter","a":0,"b":0,"g":0,"d":0,
     "HCB":50,"opDDE":0,"ppDDE":11,"opDDT":11,"ppDDT":438,
     "PCB28":9,"PCB52":2,"PCB101":1,"PCB153":0,"PCB138":0,"PCB180":0},
    {"id":"2014.10.22_B","site":"Ngari","season":"winter","a":0,"b":16,"g":3,"d":0,
     "HCB":52,"opDDE":0,"ppDDE":13,"opDDT":0,"ppDDT":620,
     "PCB28":10,"PCB52":0,"PCB101":1,"PCB153":1,"PCB138":0,"PCB180":0},
]

all_samples = lulang + namco + ngari

# ---------------------------------------------------------------------------
# Build rows
# ---------------------------------------------------------------------------
rows = []
for s in all_samples:
    hch, ddt, pcb, bdl_notes = compute(s)
    sample_id = s["id"]
    site = s["site"]
    season_note = s["season"]
    province = "Tibet"  # 西藏 (Tibetan Plateau)
    matrix = "soil"
    site_type = "other"  # remote background site

    if hch > 0:
        note = f"Table S8 Part {site}, {season_note}, Sum_HCH=a+b+g+d-HCH; {bdl_notes}"
        rows.append([PAPER_ID, sample_id, "SumHCH_ngg", str(hch), "ng/g",
                     f"Table S8 {site}", matrix, site_type, province, note])

    if ddt > 0:
        note = f"Table S8 Part {site}, {season_note}, SumDDT=o,p'-DDE+p,p'-DDE+o,p'-DDT+p,p'-DDT; {bdl_notes}"
        rows.append([PAPER_ID, sample_id, "SumDDT_ngg", str(ddt), "ng/g",
                     f"Table S8 {site}", matrix, site_type, province, note])

    if pcb > 0:
        note = f"Table S8 Part {site}, {season_note}, SumPCB=PCB28+52+101+153+138+180; {bdl_notes}"
        rows.append([PAPER_ID, sample_id, "SumPCB_ngg", str(pcb), "ng/g",
                     f"Table S8 {site}", matrix, site_type, province, note])

# ---------------------------------------------------------------------------
# Write CSV (UTF-8-sig with BOM)
# ---------------------------------------------------------------------------
header = ["paper_id","sample_id","pollutant_std","value","unit","evidence_location",
          "matrix","site_type","province","extract_notes"]

with open(OUTPUT_PATH, "w", encoding="utf-8-sig", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(header)
    for r in rows:
        writer.writerow(r)

n_rows = len(rows)
print(json.dumps({"p": PAPER_ID, "n": n_rows, "s": ""}))
print(f"Wrote {n_rows} rows to {OUTPUT_PATH}")
