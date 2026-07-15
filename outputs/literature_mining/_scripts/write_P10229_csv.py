# -*- coding: utf-8 -*-
"""Generate P10229 OP-only sampling-point CSV (UTF-8-sig)."""
import csv, os

out_path = r'C:\Users\曾鸿\Desktop\SRS\outputs\literature_mining\manual_extract\hm_op\P10229.csv'
os.makedirs(os.path.dirname(out_path), exist_ok=True)

# Table 1 PAHs (ng/g): site -> (Sum_PAH, BaP)  None = Nd
pah = {
    'S1':  (297.02, 45.63),
    'S2':  (156.5,  20.79),
    'S3':  (61.01,  12.47),
    'S4':  (80.72,  37.65),
    'S5':  (39.95,  7.79),
    'S6':  (44.24,  8.19),
    'S7':  (57.89,  15.77),
    'S8':  (36.09,  7.37),
    'S9':  (5.14,   None),   # BaP = Nd
    'R0':  (14.82,  2.89),
    'R1':  (19.19,  13.14),
    'R2':  (23.35,  4.01),
}

# Table 4 OCPs (ng/g): site -> (DDTs, HCHs)  R2 not reported
ocp = {
    'S1':  (5.15,  6.90),
    'S2':  (5.8,   2.93),
    'S3':  (3.64,  2.36),
    'S4':  (19.82, 3.62),
    'S5':  (2.4,   3.18),
    'S6':  (5.96,  1.33),
    'S7':  (2.62,  4.89),
    'S8':  (9.19,  0.76),
    'S9':  (4.54,  0.94),
    'R0':  (7.51,  3.49),
    'R1':  (25.83, 1.56),
}

site_order = ['S1','S2','S3','S4','S5','S6','S7','S8','S9','R0','R1','R2']

rows = []
for s in site_order:
    sp, bp = pah[s]
    rows.append(['P10229', s, 'Sum_PAH_ngg', sp, 'ng/g', 'Table 1',
                 'soil', 'agricultural', 'Beijing',
                 'Table1 SumPAHs列直接读(论文报告16EPA PAHs总和)'])
    if bp is not None:
        rows.append(['P10229', s, 'BaP_ngg', bp, 'ng/g', 'Table 1',
                     'soil', 'agricultural', 'Beijing',
                     'Table1 BaP(5环苯并[a]芘)直接读'])
    if s in ocp:
        ddt, hch = ocp[s]
        rows.append(['P10229', s, 'SumDDT_ngg', ddt, 'ng/g', 'Table 4',
                     'soil', 'agricultural', 'Beijing',
                     'Table4 DDTs列(DDT+DDE+DDD总和)直接读'])
        rows.append(['P10229', s, 'SumHCH_ngg', hch, 'ng/g', 'Table 4',
                     'soil', 'agricultural', 'Beijing',
                     'Table4 HCHs列(alpha+beta+gamma+delta-HCH)直接读'])

header = ['paper_id','sample_id','pollutant_std','value','unit',
          'evidence_location','matrix','site_type','province','extract_notes']

with open(out_path, 'w', encoding='utf-8-sig', newline='') as f:
    w = csv.writer(f)
    w.writerow(header)
    w.writerows(rows)

print(f'Done: {len(rows)} data rows -> {out_path}')
print('Breakdown:')
print(f'  Sum_PAH_ngg: 12 (all sites)')
print(f'  BaP_ngg:     11 (S9 BaP=Nd skipped)')
print(f'  SumDDT_ngg:  11 (R2 not reported in Table 4)')
print(f'  SumHCH_ngg:  11 (R2 not reported in Table 4)')
