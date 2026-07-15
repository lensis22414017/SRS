export const meta = {
  name: 'coord-extract-220papers',
  description: 'Agent reads paper.md Methods extracts lat/lon coordinates for each sampling site',
  phases: [{ title: 'Extract', detail: 'Agent reads paper.md StudyArea/Methods extracts coordinates' }],
}
const R = {type:'object',properties:{p:{type:'string'},n:{type:'integer'},coords:{type:'string'}},required:['p','n']}
phase('Extract')
const P = Array.isArray(args) ? args : (typeof args === 'string' ? JSON.parse(args) : [])
log('Extracting coordinates for ' + P.length + ' papers')
const r = await pipeline(P, x => agent(
  'For paper_id ' + x.p + ' with stem ' + x.s + ', extract GPS coordinates (latitude, longitude) from the full text. ' +
  'Step 1: Read paper.md from G:/文献整理_最终/' + x.s + '/parsed/paper.md (first 12000 characters should cover Abstract+StudyArea+Methods). If path encoding fails, try Glob G:/**/' + x.s + '/parsed/paper.md. ' +
  'Step 2: Find the "Study Area" or "Materials and Methods" or "Sampling" section. ' +
  'Step 3: Look for coordinate formats: N34°20\'15\" / 34.5°N / 116.8°E / latitude 34.5° / longitude 116.8° / 东经116° / 北纬34° / (34.5°N, 116.8°E) / E116°50\' / N34°20\' / GPS: (34.50, 116.80). Chinese papers use 东经 and 北纬. ' +
  'Step 4: Extract ALL unique sampling site coordinates. If the paper has a Table 1 listing all sites with coordinates, extract each site name + lat + lon. Format as JSON array: [{"site":"S1","lat":34.5,"lon":116.8},...]. ' +
  'If only one study area with a centroid coordinate, extract that single coordinate. ' +
  'If no coordinates found (only city/province names without lat/lon numbers), return coords empty string. ' +
  'Do NOT report city names (Beijing/Shanghai) as coordinates — must have numeric lat/lon. ' +
  'Return JSON: p=paper_id, n=number of coordinate pairs extracted, coords=JSON string of [{site, lat, lon}].',
  {label: x.p, schema: R}
))
const ok = r.filter(Boolean).filter(x => x.n > 0)
log('Done: ' + r.filter(Boolean).length + '/' + P.length + ', coord papers: ' + ok.length + ', coord pairs: ' + ok.reduce((a,b) => a + b.n, 0))
return {processed: r.filter(Boolean).length, withCoords: ok.length, totalPairs: ok.reduce((a,b) => a + b.n, 0), papers: ok}
