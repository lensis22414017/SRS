"""Smart coordinate matching: centroid broadcast + site name fuzzy matching."""
import sys, os, json, csv, re
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

ME = r'C:/Users/曾鸿/Desktop/SRS/outputs/literature_mining/manual_extract/op_only'
BASE = r'C:/Users/曾鸿/.claude/projects/C--Users---/256efec4-085c-4e28-a198-da065f46a8b0/subagents/workflows'

all_coord_results = []
for wf in ['wf_b44e42e6-2ae','wf_edd4abce-2cf']:
    jd = BASE + '/' + wf + '/journal.jsonl'
    if not os.path.exists(jd): continue
    with open(jd, encoding='utf-8') as f:
        for l in f:
            if '"type":"result"' not in l: continue
            r = json.loads(l).get('result',{}) or {}
            if r.get('n',0) > 0 and r.get('coords'):
                all_coord_results.append(r)

print(f'Total coord papers from both WFs: {len(all_coord_results)}')

updated_papers = 0
updated_rows = 0

for r in all_coord_results:
    p = r['p']
    try: coords = json.loads(r['coords'])
    except: continue
    if not coords: continue

    csv_f = ME + '/' + p + '.csv'
    if not os.path.exists(csv_f): continue

    with open(csv_f, newline='', encoding='utf-8-sig') as fh:
        rows = list(csv.DictReader(fh))
    if not rows: continue

    # Ensure lat/lon columns
    for row in rows:
        if 'latitude' not in row: row['latitude'] = ''
        if 'longitude' not in row: row['longitude'] = ''

    # Strategy 1: exact match by site name (strip suffixes like _SKIP/NOTES)
    coord_map = {}
    for c in coords:
        sid = c.get('site','').strip()
        if sid: coord_map[sid] = (str(c.get('lat','')), str(c.get('lon','')))

    modified = False
    rows_updated = 0

    # Try exact + fuzzy match per row
    for row in rows:
        sid = row.get('sample_id','').strip()
        if sid in coord_map:
            row['latitude'] = coord_map[sid][0]
            row['longitude'] = coord_map[sid][1]
            modified = True; rows_updated += 1; continue

        # Fuzzy: strip _SKIP/_NOTES suffix
        clean = sid.split('_')[0] if '_' in sid else sid
        if clean in coord_map and clean != sid:
            row['latitude'] = coord_map[clean][0]
            row['longitude'] = coord_map[clean][1]
            modified = True; rows_updated += 1; continue

        # Try partial match: site name substring in coord keys or vice versa
        for ckey, (lat,lon) in coord_map.items():
            if ckey.lower() in sid.lower() or sid.lower() in ckey.lower():
                row['latitude'] = lat
                row['longitude'] = lon
                modified = True; rows_updated += 1; break

    # Strategy 2: Centroid broadcast — if only 1-3 coords and they look like study area centroids,
    # broadcast to ALL rows in the CSV
    centroid_keywords = ['centroid','study','area','中心','研究区','studyarea','center','site','approx']
    is_centroid = all(
        any(kw in c.get('site','').lower() for kw in centroid_keywords)
        for c in coords
    )
    n_rows = len([r for r in rows if r.get('sample_id','').strip()])

    if (len(coords) <= 3 and n_rows > 1) or is_centroid:
        if not modified:
            # Take first coord as centroid
            lat = str(coords[0].get('lat',''))
            lon = str(coords[0].get('lon',''))
            if lat and lon:
                for row in rows:
                    sid = row.get('sample_id','').strip()
                    if sid and row['latitude'] == '' and row['longitude'] == '':
                        row['latitude'] = lat
                        row['longitude'] = lon
                        modified = True; rows_updated += 1

    if modified:
        # Clean None keys from rows
        clean_rows = [{k:v for k,v in row.items() if k is not None} for row in rows]
        fieldnames = list(clean_rows[0].keys())
        with open(csv_f, 'w', newline='', encoding='utf-8-sig') as fh:
            w = csv.DictWriter(fh, fieldnames=fieldnames)
            w.writeheader()
            for row in clean_rows:
                # Ensure all fields present
                safe_row = {k: row.get(k, '') for k in fieldnames}
                w.writerow(safe_row)
        updated_papers += 1
        updated_rows += rows_updated
        print(f'{p}: {rows_updated} rows updated (coords={len(coords)})')

print(f'\nTotal: {updated_papers} papers, {updated_rows} rows with coordinates')
