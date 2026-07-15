"""P02403 SI CSV extraction: 27 sites × 16 PAH monomers + PCBs + OCPs."""
import sys, csv, os
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import pandas as pd
import numpy as np

si_fp = r'G:/文献整理_最终/10.1080_09603123.2011.634392/si/T0001-10.1080_09603123.2011.634392.csv'
df = pd.read_csv(si_fp)

# Row 0 = site labels
sites_raw = [str(s).strip().replace('.0','') for s in df.iloc[0, 2:].values if str(s) != 'nan']
print(f'Sites: {len(sites_raw)} → {sites_raw}')

# Compound-to-standard mapping
NAME_MAP = {
    'Nap':'Nap','Acpy':'Acy','Acp':'Ace','Flu':'Flu','Pa':'Phe','Ant':'Ant',
    'Fl':'Flt','Pyr':'Pyr','Baa':'BaA','Chr':'Chr','Bbf':'BbF','Bkf':'BkF',
    'Bap':'BaP','Ind':'IcdP','Dba':'DahA','Bghip':'BghiP',
    'PCB-28':'PCB28','PCB-52':'PCB52','PCB-101':'PCB101','PCB-138':'PCB138',
    'PCB-153':'PCB153','PCB-180':'PCB180',
    'p,p-DDE':'p,p-DDE','p,p-DDD':'p,p-DDD','p,p-DDT':'p,p-DDT',
    'o,p-DDE':'o,p-DDE','o,p-DDD':'o,p-DDD','o,p-DDT':'o,p-DDT',
    'alpha-HCH':'α-HCH','gamma-HCH':'γ-HCH','delta-HCH':'δ-HCH',
    'Endosulfan':'Endosulfan','Hexachlorobenzene':'HCB',
    'Atrazine':'Atrazine','Chlorobenzilate':'Chlorobenzilate','Dicofol':'Dicofol',
    'Heptachlor':'Heptachlor',
}

# Parse compound rows
rows = []
for i in range(1, len(df)):
    compound_raw = str(df.iloc[i, 1]).strip().replace(' ','').replace('​','')
    if not compound_raw or compound_raw == 'nan': continue
    mapped = NAME_MAP.get(compound_raw, compound_raw)

    for j in range(2, len(df.columns)):
        v = df.iloc[i, j]
        if pd.isna(v) or str(v).strip() in ('', '-'): continue
        try:
            val = float(str(v).replace(',', '.'))
            site = sites_raw[j-2]
            # Use standard PAH monomer suffix
            if mapped in ('Nap','Acy','Ace','Flu','Phe','Ant','Flt','Pyr','BaA','Chr','BbF','BkF','BaP','IcdP','DahA','BghiP'):
                cols = f'{mapped}_ngg'
            elif mapped.startswith('PCB'):
                cols = f'{mapped}_ngg'
            elif 'DD' in mapped or 'HCH' in mapped or 'Endo' in mapped or mapped in ('HCB','Atrazine','Chlorobenzilate','Dicofol','Heptachlor'):
                cols = f'{mapped}_ngg'
            else:
                cols = f'{mapped}_ngg'
            rows.append({
                'paper_id': 'P02403',
                'sample_id': site,
                'pollutant_std': cols,
                'value': f'{val:.2f}',
                'unit': 'ng/g',
                'evidence_location': 'SI Table T0001 (supplementary CSV)',
                'matrix': 'soil',
                'site_type': 'e_waste',
                'province': 'Zhejiang',
                'extract_notes': f'SI CSV direct read; compound={compound_raw}; 27 sites x 37 compounds matrix; original unit ng/g'
            })
        except: pass

# Save NEW CSV — only the monomer data (not Sum_* which was already extracted)
df_new = pd.DataFrame(rows)
# Exclude already-extracted: P02403 existing has Sum_PAH/BaP/SumPCB/SumHCH/SumDDT
EXISTING_COLS = {'Sum_PAH_ngg','BaP_ngg','SumPCB_ngg','SumHCH_ngg','SumDDT_ngg'}
new_only = df_new[~df_new['pollutant_std'].isin(EXISTING_COLS)]
print(f'\nTotal SI rows: {len(df_new)}')
print(f'New (not in existing Sum_*): {len(new_only)} rows')

# Summarize by compound
for col in sorted(new_only['pollutant_std'].unique()):
    n = len(new_only[new_only['pollutant_std']==col])
    print(f'  {col}: {n}')

out = r'C:/Users/曾鸿/Desktop/SRS/outputs/literature_mining/manual_extract/op_only/P02403_SI_monomers.csv'
new_only.to_csv(out, index=False, encoding='utf-8-sig')
print(f'\nSaved to {out}')

# Show sample values
print('\n=== Sample data (first 10 rows) ===')
print(new_only.head(10).to_string())
