"""
Parse antiword output for P00624 supplementary tables
"""
import re, json, os, csv, io, sys

with open(r'G:\文献整理_最终\10.1007_s11356-015-4230-3\si\si_raw.txt', 'r', encoding='latin1') as f:
    data = f.read()

# Table boundaries (second occurrence of each table title)
ranges = {
    'S3': (6588, 12841),
    'S4': (12841, 17218),
    'S5': (17218, 22435),
    'S6': (22435, len(data)),
}

def parse_table_tokens(text, start, end, col_names):
    """Parse pipe-delimited antiword table into {sample_id: {col: value}}."""
    section = text[start:end]

    # Split by pipe character
    tokens = [t.strip() for t in section.split('|')]
    tokens = [t for t in tokens if t]

    # Find first sample ID (B\d+ or S\d+)
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

        # Check for sample ID
        m = re.match(r'^([BS]\d+)$', t)
        if m:
            # Save previous row
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

        # Check if value is numeric
        t_clean = t.lower()
        t_clean = re.sub(r'[\s ]', '', t_clean)

        if t_clean in ('nd', 'n.d.', '-', ''):
            current_col += 1
            continue

        # Replace comma decimal separator, remove non-numeric
        t_num = t_clean.replace(',', '.')
        try:
            val = float(t_num)
            current_vals[col_names[current_col]] = val
            current_col += 1
        except ValueError:
            # Skip non-numeric tokens (continuation lines, footnotes, etc.)
            pass

    # Save last row
    if current_sid and current_vals:
        rows[current_sid] = current_vals

    return rows

# Column definitions
s3_cols = ['NOR', 'OFL', 'CIP', 'DIF', 'ENR', 'FLE', 'LOM', 'SAR',
           'SMX', 'SPD', 'SMZ', 'SDZ', 'SMM', 'SPI', 'JOS', 'TYL', 'ROX', 'ERY']
s4_cols = ['NOR', 'OFL', 'CIP', 'DIF', 'ENR', 'FLE', 'LOM', 'SAR',
           'SMX', 'SMZ', 'SDZ', 'SMM', 'SPI', 'ROX', 'ERY']
s56_cols = ['pH', 'TOC_pct', 'Fe_ugg', 'Ti_ugg', 'Mn_ugg',
            'Zn_ugg', 'V_ugg', 'Cu_ugg', 'Cd_ugg', 'Pb_ugg']

bj_ab = parse_table_tokens(data, *ranges['S3'], s3_cols)
sh_ab = parse_table_tokens(data, *ranges['S4'], s4_cols)
bj_hm = parse_table_tokens(data, *ranges['S5'], s56_cols)
sh_hm = parse_table_tokens(data, *ranges['S6'], s56_cols)

print(f'BJ AB: {len(bj_ab)} samples')
print(f'SH AB: {len(sh_ab)} samples')
print(f'BJ HM: {len(bj_hm)} samples')
print(f'SH HM: {len(sh_hm)} samples')

print()
print('BJ AB B1:', json.dumps(bj_ab.get('B1', {})))
print('BJ AB B64:', json.dumps(bj_ab.get('B64', {})))
print('BJ HM B1:', json.dumps(bj_hm.get('B1', {})))
print('BJ HM B64:', json.dumps(bj_hm.get('B64', {})))
print('SH AB S1:', json.dumps(sh_ab.get('S1', {})))
print('SH AB S27:', json.dumps(sh_ab.get('S27', {})))
print('SH HM S1:', json.dumps(sh_hm.get('S1', {})))
print('SH HM S40:', json.dumps(sh_hm.get('S40', {})))

# Check matches between AB and HM
bj_ab_ids = set(bj_ab.keys())
bj_hm_ids = set(bj_hm.keys())
sh_ab_ids = set(sh_ab.keys())
sh_hm_ids = set(sh_hm.keys())

print(f'\nBJ AB-only: {sorted(bj_ab_ids - bj_hm_ids)}')
print(f'BJ HM-only: {sorted(bj_hm_ids - bj_ab_ids)}')
print(f'BJ overlap: {len(bj_ab_ids & bj_hm_ids)}')
print(f'\nSH AB-only: {sorted(sh_ab_ids - sh_hm_ids)}')
print(f'SH HM-only: {sorted(sh_hm_ids - sh_ab_ids)}')
print(f'SH overlap: {len(sh_ab_ids & sh_hm_ids)}')
