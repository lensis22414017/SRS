"""
Extract sampling-point level OP (antibiotics) and HM data for P00624.
Paper: Gao et al. 2015. Occurrence and distribution of antibiotics in urban soil in Beijing and Shanghai, China.
DOI: 10.1007/s11356-015-4230-3

Data sources:
- Table S3: Beijing antibiotics (B1-B69, ug/kg dw)
- Table S4: Shanghai antibiotics (S1-S55, ug/kg dw)
- Table S5: Beijing soil characterization (HM in ug/g = mg/kg)
- Table S6: Shanghai soil characterization (HM in ug/g = mg/kg)

OP targets from extraction rules: SMZ, SDZ, ENRO(=ENR=Enrofloxacin), CTC, OTC.
  Paper detects SMZ, SDZ, ENR. No CTC/OTC.

HM targets: Cd, Pb, Cr, As, Hg, Cu, Zn, Ni.
  Paper detects: Cd, Pb, Cu, Zn in Tables S5/S6 (as ug/g = mg/kg).
  Not detected: Cr, As, Hg, Ni.
"""
import re, json, os, csv, io, sys

with open(r'G:\文献整理_最终\10.1007_s11356-015-4230-3\si\si_raw.txt', 'r', encoding='latin1') as f:
    data = f.read()

ranges = {
    'S3': (6588, 12841),
    'S4': (12841, 17218),
    'S5': (17218, 22435),
    'S6': (22435, len(data)),
}

def parse_table_tokens(text, start, end, col_names):
    """Parse pipe-delimited antiword table into {sample_id: {col: value}}."""
    section = text[start:end]
    tokens = [t.strip() for t in section.split('|')]
    tokens = [t for t in tokens if t]

    data_start = -1
    for i, t in enumerate(tokens):
        if re.match(r'^[BS]\d+$', t):
            data_start = i
            break
    if data_start < 0:
        return {}

    n_cols = len(col_names)
    rows = {}
    current_sid = None
    current_col = 0
    current_vals = {}

    for i in range(data_start, len(tokens)):
        t = tokens[i].strip()
        m = re.match(r'^([BS]\d+)$', t)
        if m:
            if current_sid and current_vals:
                rows[current_sid] = current_vals
            current_sid = m.group(1)
            current_col = 0
            current_vals = {}
            continue
        if 'nd:' in t:
            break
        if current_sid is None:
            continue
        if current_col >= n_cols:
            continue
        t_clean = t.lower()
        t_clean = re.sub(r'[\s\xa0]', '', t_clean)
        if t_clean in ('nd', 'n.d.', '-', ''):
            current_col += 1
            continue
        t_num = t_clean.replace(',', '.')
        try:
            val = float(t_num)
            current_vals[col_names[current_col]] = val
            current_col += 1
        except ValueError:
            pass

    if current_sid and current_vals:
        rows[current_sid] = current_vals
    return rows

s3_cols = ['NOR','OFL','CIP','DIF','ENR','FLE','LOM','SAR','SMX','SPD','SMZ','SDZ','SMM','SPI','JOS','TYL','ROX','ERY']
s4_cols = ['NOR','OFL','CIP','DIF','ENR','FLE','LOM','SAR','SMX','SMZ','SDZ','SMM','SPI','ROX','ERY']
s56_cols = ['pH','TOC_pct','Fe_ugg','Ti_ugg','Mn_ugg','Zn_ugg','V_ugg','Cu_ugg','Cd_ugg','Pb_ugg']

bj_ab = parse_table_tokens(data, *ranges['S3'], s3_cols)
sh_ab = parse_table_tokens(data, *ranges['S4'], s4_cols)
bj_hm = parse_table_tokens(data, *ranges['S5'], s56_cols)
sh_hm = parse_table_tokens(data, *ranges['S6'], s56_cols)

print(f'BJ AB: {len(bj_ab)}, SH AB: {len(sh_ab)}, BJ HM: {len(bj_hm)}, SH HM: {len(sh_hm)}')

# OP mapping: column_name -> pollutant_std
op_map = {
    'SMZ': 'SMZ_ngg',
    'SDZ': 'SDZ_ngg',
    'ENR': 'ENRO_ngg',  # Enrofloxacin
}

# HM mapping: column_name -> pollutant_std
hm_map = {
    'Cd_ugg': 'Cd_mgkg',
    'Pb_ugg': 'Pb_mgkg',
    'Cu_ugg': 'Cu_mgkg',
    'Zn_ugg': 'Zn_mgkg',
}

# Build output rows
output_rows = []

for city, ab_data, hm_data in [
    ('Beijing', bj_ab, bj_hm),
    ('Shanghai', sh_ab, sh_hm),
]:
    province = '北京' if city == 'Beijing' else '上海'
    common_ids = sorted(set(ab_data.keys()) & set(hm_data.keys()))
    print(f'{city}: {len(common_ids)} samples with both AB and HM')

    for sid in common_ids:
        ab_vals = ab_data[sid]
        hm_vals = hm_data[sid]

        # OP antibiotics (ug/kg = ng/g, value unchanged)
        for ab_col, pol_std in op_map.items():
            if ab_col in ab_vals:
                val = ab_vals[ab_col]
                output_rows.append({
                    'paper_id': 'P00624',
                    'sample_id': sid,
                    'pollutant_std': pol_std,
                    'value': val,
                    'unit': 'ng/g',
                    'evidence_location': f'Table S{"3" if city == "Beijing" else "4"}',
                    'matrix': 'soil',
                    'site_type': 'urban',
                    'province': province,
                    'extract_notes': f'{city}城市土壤, 直接从补充材料表读取, 单位ug/kg=ng/g'
                })

        # HM (ug/g = mg/kg, value unchanged)
        for hm_col, pol_std in hm_map.items():
            if hm_col in hm_vals:
                val = hm_vals[hm_col]
                # Skip unreasonably large values (Fe, Ti, Mn, etc.)
                output_rows.append({
                    'paper_id': 'P00624',
                    'sample_id': sid,
                    'pollutant_std': pol_std,
                    'value': val,
                    'unit': 'mg/kg',
                    'evidence_location': f'Table S{"5" if city == "Beijing" else "6"}',
                    'matrix': 'soil',
                    'site_type': 'urban',
                    'province': province,
                    'extract_notes': f'{city}城市土壤, 直接从补充材料表读取, 单位ug/g=mg/kg'
                })

print(f'Total output rows: {len(output_rows)}')

# Write CSV
out_dir = r'C:\Users\曾鸿\Desktop\SRS\outputs\literature_mining\manual_extract\op_only'
os.makedirs(out_dir, exist_ok=True)
out_path = os.path.join(out_dir, 'P00624.csv')

with open(out_path, 'w', newline='', encoding='utf-8-sig') as f:
    writer = csv.DictWriter(f, fieldnames=[
        'paper_id','sample_id','pollutant_std','value','unit',
        'evidence_location','matrix','site_type','province','extract_notes'
    ])
    writer.writeheader()
    for row in output_rows:
        writer.writerow(row)

print(f'Written to: {out_path}')

# Summary stats
n_samples = len(set(r['sample_id'] for r in output_rows))
bj_count = len([r for r in output_rows if '北京' in r['extract_notes']])
sh_count = len([r for r in output_rows if '上海' in r['extract_notes']])
op_count = len([r for r in output_rows if r['pollutant_std'].endswith('_ngg')])
hm_count = len([r for r in output_rows if r['pollutant_std'].endswith('_mgkg')])

print(f'\nSummary:')
print(f'  Unique sample IDs: {n_samples}')
print(f'  Beijing rows: {bj_count}')
print(f'  Shanghai rows: {sh_count}')
print(f'  OP (antibiotic) rows: {op_count}')
print(f'  HM rows: {hm_count}')
print(f'  Total rows: {len(output_rows)}')

# Print JSON result
result = {'p': 'P00624', 'n': len(output_rows), 's': ''}
print(f'\nRESULT_JSON: {json.dumps(result, ensure_ascii=False)}')
