export const meta = {
  name: 'extract-土壤候选-精读',
  description: '对筛选命中的soil候选论文精读paper.md提取OP/HM+OP采样点数据',
  phases: [{ title: 'Extract', detail: 'Agent reads paper.md extracts OP/HM+OP data to CSV' }],
}
const R = {type:'object',properties:{p:{type:'string'},n:{type:'integer'},s:{type:'string'}},required:['p','n']}
phase('Extract')
const P = Array.isArray(args) ? args : (typeof args === 'string' ? JSON.parse(args) : [])
log('Extracting ' + P.length + ' soil candidate papers')
const r = await pipeline(P, x => agent(
  'Find the stem for paper_id ' + x.p + ' in the CSV at ~/Desktop/SRS/outputs/literature_mining/screen_op_china_v2.csv (match column 序号 with value ' + x.p + ', get stem column). ' +
  'Then Read ~/Desktop/SRS/outputs/literature_mining/_scripts/agent_extract_prompt.md for extraction rules. ' +
  'The paper.md is at G:/literature_final/{stem}/parsed/paper.md. If Chinese path chars cause issues, use Glob G:/**/{stem}/parsed/paper.md to locate it. ' +
  'Extract real sampling-point level organic pollutant data (OP) AND heavy metal data (HM) if available at the same sampling sites. ' +
  'OP pollutants: Sum_PAH_ngg(=16 EPA PAH sum), BaP_ngg, SumPCB_ngg, SumDDT_ngg, SumHCH_ngg, SumPBDE_ngg, TotalPHC_mgkg; antibiotics SMZ/SDZ/ENRO/CTC/OTC; PAEs DBP/DEHP/DEP/DiBP/SumPAE; OCPs Endosulfan/OCP_total. Units: ng/g for OP, mg/kg for petroleum (TotalPHC). ' +
  'HM pollutants: Cd_mgkg, Pb_mgkg, Cr_mgkg, As_mgkg, Hg_mgkg, Cu_mgkg, Zn_mgkg, Ni_mgkg. Units: mg/kg. ' +
  'Reject: stat rows(Mean/SD/Max/Min/Median/CV/Range), thresholds(Grade/GB15618/GB36600/Dutch), risk indices(HQ/TEQ/Nemerow/RI/Igeo), pot/greenhouse/spiked, water, air, plant tissue, remediation effects(extract pre-remediation baseline only), non-China sites. ' +
  'Output CSV(UTF-8-sig with BOM) to ~/Desktop/SRS/outputs/literature_mining/manual_extract/op_only/' + x.p + '.csv ' +
  'Header: paper_id,sample_id,pollutant_std,value,unit,evidence_location,matrix,site_type,province,extract_notes. ' +
  'sample_id = original paper labels (S1/A/B/village name). For OP units: ug/kg=ng/g(value unchanged), mg/kg×1000=ng/g. Wrap extract_notes commas in double quotes. Sediment=matrix:sediment. ' +
  'If no sample-level data, output empty CSV with header only plus one notes row. ' +
  'Return JSON: p=paper_id, n=data rows extracted, s=skip reason if n is 0.',
  {label: x.p, schema: R}
))
const ok = r.filter(Boolean).filter(x => x.n > 0)
log('Done ' + r.filter(Boolean).length + '/' + P.length + ', ok ' + ok.length + ', samples ' + ok.reduce((a,b) => a + b.n, 0))
return {processed: r.filter(Boolean).length, success: ok.length, samples: ok.reduce((a,b) => a + b.n, 0)}
