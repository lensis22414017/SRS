export const meta = {
  name: 'screen-标题摘要-初筛',
  description: '基于标题+op_groups判断论文是否含土壤OP/HM+OP采样数据',
  phases: [{ title: 'Classify', detail: 'Agent reads title judges soil data potential' }],
}
const R = {type:'object',properties:{p:{type:'string'},v:{type:'string',enum:['soil_OP','soil_HMOP','skip']},r:{type:'string'}},required:['p','v','r']}
phase('Classify')
const P = Array.isArray(args) ? args : (typeof args === 'string' ? JSON.parse(args) : [])
log('Classifying ' + P.length + ' papers by title/op_groups')
const r = await pipeline(P, x => agent(
  'You are screening papers for a Chinese soil pollution training dataset. ' +
  'For paper_id ' + x.p + ', evaluate: stem=' + x.stem + ', en_title=' + x.en_title.slice(0,200) + ', zh_title=' + (x.zh_title||'').slice(0,200) + ', op_groups=' + x.op_groups + '.' +
  'EN_TITLE:=' + x.en_title.slice(0,300) + '. ZH_TITLE:=' + (x.zh_title||'').slice(0,300) + '.' +
  ' Classify as one of: ' +
  ' - "soil_OP": likely has real sampling-point-level organic pollutant (PAH/PCB/DDT/HCH/PBDE/PHC/antibiotics/PAE) concentration data for Chinese soil (not water/air/plant/pot experiment/review/modeling). Keywords like "soil contamination", "soil pollution", "agricultural soil", "e-waste soil", "coking site", "industrial park soil" are strong signals. ' +
  ' - "soil_HMOP": same as soil_OP but likely has BOTH heavy metals AND organic pollutants measured at same sampling sites. Keywords like "heavy metal and PAH", "Cd and PCB", "metal and organic co-contamination". ' +
  ' - "skip": clearly not soil sampling data — water/sediment-only/aquatic/plant tissue/atmosphere/pot experiment/spiked/review/model/GIS/health risk without new measurement data/method development/carbon nanotubes/adsorption kinetics/pure chemistry. ' +
  'Return JSON: v=classification, r=brief Chinese reason (1 sentence).',
  {label: x.p, schema: R}
));
const classified = r.filter(Boolean);
const soil = classified.filter(x => x.v !== 'skip');
log('Done ' + classified.length + '/' + P.length + ': soil_OP=' + classified.filter(x=>x.v==='soil_OP').length + ' soil_HMOP=' + classified.filter(x=>x.v==='soil_HMOP').length + ' skip=' + classified.filter(x=>x.v==='skip').length);
return {total: classified.length, soil: soil.length, details: classified.filter(x => x.v !== 'skip').map(x=>({p: P.find(y=>y.p===x.label)?.p||x.label, v:x.v, r:x.r}))};
