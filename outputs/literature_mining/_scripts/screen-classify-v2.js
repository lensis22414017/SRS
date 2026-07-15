export const meta = {
  name: 'screen-v2-标题摘要筛选',
  description: 'Agent自读paper.md摘要+screen CSV做三分类(soil_OP/soil_HMOP/skip)',
  phases: [{ title: 'Classify', detail: 'Agent reads abstract classifies soil data potential' }],
}
const R = {type:'object',properties:{p:{type:'string'},v:{type:'string',enum:['soil_OP','soil_HMOP','skip']},r:{type:'string'}},required:['p','v','r']}
phase('Classify')
const P = Array.isArray(args) ? args : (typeof args === 'string' ? JSON.parse(args) : [])
log('Classifying ' + P.length + ' papers (agent reads abstract+CSV)')
const r = await pipeline(P, x => agent(
  'Classify paper_id=' + x.p + ' (stem=' + x.s + ') for Chinese soil pollution training dataset. ' +
  'Step1: Read the screen CSV at ~/Desktop/SRS/outputs/literature_mining/screen_op_china_v2.csv, find row where 序号=' + x.p + ', get op_groups and has_hm columns. ' +
  'Step2: Read first 60 lines of G:/literature_final/' + x.s + '/parsed/paper.md to get title and abstract. If path fails, try Glob G:/literature_final/**/' + x.s + '/parsed/paper.md. ' +
  'Classify as: ' +
  '- "soil_OP": likely has real sampling-point-level organic pollutant concentration data (PAH/PCB/DDT/HCH/PBDE/PHC/antibiotics/PAE) for Chinese SOIL (not water/air/plant/pot experiment/review/modeling). Strong signals in abstract: "soil contamination", "spatial distribution of PAHs in soil", "agricultural soil", "e-waste soil", "coking site soil", "concentration of ... in soil samples collected from ...", "n=X sampling sites". ' +
  '- "soil_HMOP": high confidence that BOTH heavy metals AND organic pollutants were measured at the SAME sampling sites. Abstract should mention BOTH HM and OP measurements. Keywords: "heavy metals and PAHs", "co-contamination", "Cd and PCB", "metal and organic pollutants in soil". If only HM data (no OP) → still classify as soil_HMOP IF has_hm=true AND the paper has real OP measurements in the soil. ' +
  '- "skip": clearly NOT real soil sampling data — water/sediment-only/aquatic/plant tissue/atmosphere/pot experiment/spiked/review/model/GIS/health risk without new measurement data/method development/carbon nanotubes/adsorption kinetics/pure chemistry/not China. Greenhouse/pot experiment: SKIP (even if mentions soil). ' +
  'Return JSON with p=' + x.p + ', v=classification, r=1-sentence Chinese reason based on abstract evidence.',
  {label: x.p, schema: R}
))
const classified = r.filter(Boolean)
const hits = classified.filter(x => x.v !== 'skip')
log('Done: total=' + classified.length + ' soil_OP=' + classified.filter(x=>x.v==='soil_OP').length + ' soil_HMOP=' + classified.filter(x=>x.v==='soil_HMOP').length + ' skip=' + classified.filter(x=>x.v==='skip').length)
return {total: classified.length, soil_OP: classified.filter(x=>x.v==='soil_OP').length, soil_HMOP: classified.filter(x=>x.v==='soil_HMOP').length, hits: hits}
