"""P04039 SI: extract GPS coordinates + pH/EC, merge with existing data."""
import sys, os
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import pandas as pd

base = r'C:/Users/曾鸿/Desktop/SRS/outputs/literature_mining/manual_extract/op_only'
existing_f = base + '/P04039.csv'

existing = pd.read_csv(existing_f, dtype=str, keep_default_na=False, on_bad_lines='skip', engine='python')
print('Existing P04039:', len(existing), 'rows')

# Load SI coordinates
si_xl = r'G:/文献整理_最终/10.3390_ijerph13090878/si/ijerph-13-00878-s001.xlsx'
coord_df = pd.read_excel(si_xl, sheet_name='data')
coord_df.columns = ['sample_id_raw','latitude','longitude','pH','EC_uS_cm']

SITE_MAP = {'px-1':'px1','px-2':'px2','px-3':'px3','px-4':'px4','px-5':'px5','px-6':'px6','px-7':'px7',
    'hr-1':'hr1','hr-2':'hr2','hr-3':'hr3','dt-1':'dt1','dt-2':'dt2','dt-3':'dt3',
    'hm-1':'hm1','hm-2':'hm2','hm-3':'hm3','yz-1':'yz1','yz-2':'yz2','yz-3':'yz3',
    'qt-1':'qt1','qt-2':'qt2','qt-3':'qt3','qt-4':'qt4'}

coord_df['sample_id'] = coord_df['sample_id_raw'].map(SITE_MAP)
print('Coordinates:', len(coord_df), 'points')

# Build coord lookup
coord_lookup = {}
for _, r in coord_df.iterrows():
    sid = r['sample_id']
    lat = str(r['latitude']) if pd.notna(r['latitude']) else ''
    lon = str(r['longitude']) if pd.notna(r['longitude']) else ''
    ph = str(round(float(r['pH']), 2)) if pd.notna(r['pH']) else ''
    ec = str(round(float(r['EC_uS_cm']), 1)) if pd.notna(r['EC_uS_cm']) else ''
    coord_lookup[sid] = (lat, lon, ph, ec)

# Add lat/lon columns to existing CSV
if 'latitude' not in existing.columns:
    existing['latitude'] = ''
    existing['longitude'] = ''

updated_count = 0
for idx in existing.index:
    sid = existing.at[idx, 'sample_id']
    if sid in coord_lookup:
        lat, lon, _, _ = coord_lookup[sid]
        if lat:
            existing.at[idx, 'latitude'] = lat
            existing.at[idx, 'longitude'] = lon
            updated_count += 1

existing.to_csv(existing_f, index=False, encoding='utf-8-sig')
print('Updated', updated_count, 'rows with coordinates')
print('Saved:', existing_f)

# Add pH + EC as new CSV
ph_ec_rows = []
for sid, (lat, lon, ph, ec) in coord_lookup.items():
    raw = SITE_MAP.get(sid, sid)
    note = 'SI xlsx data sheet; site=' + str(sid) + '; GPS: ' + str(lat) + ', ' + str(lon)
    if ph:
        ph_ec_rows.append({'paper_id':'P04039','sample_id':sid,'pollutant_std':'pH','value':ph,'unit':'',
            'evidence_location':'SI Table (ijerph-13-00878-s001.xlsx)','matrix':'soil','site_type':'industrial',
            'province':'Jiangsu','latitude':lat,'longitude':lon,'extract_notes':note})
    if ec:
        ph_ec_rows.append({'paper_id':'P04039','sample_id':sid,'pollutant_std':'EC_uScm','value':ec,'unit':'uS/cm',
            'evidence_location':'SI Table (ijerph-13-00878-s001.xlsx)','matrix':'soil','site_type':'industrial',
            'province':'Jiangsu','latitude':lat,'longitude':lon,'extract_notes':note})

if ph_ec_rows:
    ph_ec_df = pd.DataFrame(ph_ec_rows)
    ph_ec_df.to_csv(base + '/P04039_pH_EC.csv', index=False, encoding='utf-8-sig')
    print('pH/EC data:', len(ph_ec_df), 'rows')
