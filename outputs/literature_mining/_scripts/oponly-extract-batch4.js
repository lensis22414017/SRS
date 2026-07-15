export const meta = {
  name: 'oponly-extract-batch4',
  description: 'Extract OP-only sampling data from 200 papers (batch4)',
  phases: [{ title: 'Extract', detail: 'Agent reads paper.md extracts OP data' }],
}
const R = {type:'object',properties:{p:{type:'string'},n:{type:'integer'},s:{type:'string'}},required:['p','n']}
phase('Extract')
const P = typeof args === 'string' ? JSON.parse(args) : (Array.isArray(args) ? args : [])
log('Processing ' + P.length + ' OP-only papers (batch4)')
const r = await pipeline(P, x => agent(
  'Find the stem for paper_id ' + x + ' in the CSV at ~/Desktop/SRS/outputs/literature_mining/screen_op_china_v2.csv (match column "序号" with value x, get "stem" column). ' +
  'Then Read ~/Desktop/SRS/outputs/literature_mining/_scripts/agent_extract_prompt.md for extraction rules. ' +
  'Then Read the paper at the path G:/literature_final/{stem}/parsed/paper.md - if Chinese path chars cause issues use Glob G:/**/{stem}/parsed/paper.md to locate it. ' +
  'Extract real sampling-point level OP(Sum_PAH_ngg=16 EPA PAH monomer sum Nap/Acy/Ace/Flu/Phe/Ant/Flt/Pyr/BaA/Chr/BbF/BkF/BaP/IcdP/DahA/BghiP, BaP_ngg, SumPCB_ngg=PCB monomers/homologs sum, SumDDT_ngg=DDT+DDE+DDD, SumHCH_ngg=alpha+beta+gamma+delta, SumPBDE_ngg, TotalPHC_mgkg; antibiotics SMZ/SDZ/ENRO/CTC/OTC; PAEs DBP/DEHP/DEP/DiBP/SumPAE; OCPs Endosulfan/OCP_total; units ng/g for OP and mg/kg for petroleum). ' +
  'Reject: stat rows(Mean/SD/Max/Min/Median/CV/Range), thresholds(Grade/GB15618/GB36600/Dutch optimum/action), risk indices(HQ/TEQ/Nemerow/RI/Igeo/pollution index), pot/greenhouse/spiked experiments, water, air, plant tissue, remediation effects, non-China sites. ' +
  'For remediation papers extract pre-remediation site baseline if available. ' +
  'Output CSV(UTF-8-sig with BOM) to ~/Desktop/SRS/outputs/literature_mining/manual_extract/op_only/' + x + '.csv ' +
  'Header: paper_id,sample_id,pollutant_std,value,unit,evidence_location,matrix,site_type,province,extract_notes. ' +
  'sample_id = original paper labels (S1/A/B/village name). Never use concentration values or stat names as sample_id. ' +
  'For OP units: ug/kg equals ng/g (value unchanged), mg/kg times 1000 equals ng/g. Wrap extract_notes commas in double quotes. Sediment = matrix:sediment. ' +
  'If no sample-level data (only stat summaries or pot experiments or figures), output empty CSV with header only plus one notes row. ' +
  'Return JSON: p=paper_id, n=data rows extracted, s=skip reason if n is 0.',
  {label: x, schema: R}
))
const ok = r.filter(Boolean).filter(x => x.n > 0)
log('Done ' + r.filter(Boolean).length + '/' + P.length + ', ok ' + ok.length + ', samples ' + ok.reduce((a,b) => a + b.n, 0))
return {processed: r.filter(Boolean).length, success: ok.length, samples: ok.reduce((a,b) => a + b.n, 0)}
