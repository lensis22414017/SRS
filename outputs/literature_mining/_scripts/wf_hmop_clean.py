"""Generate clean workflow script for HM+OP remaining papers"""
import json, re
from pathlib import Path

hmop = json.load(open(r"C:\Users\曾鸿\Desktop\SRS\outputs\literature_mining\_scripts\hmop_remaining.json", encoding="utf-8"))
papers_mini = [{"paper_id": p["paper_id"], "stem": p["stem"]} for p in hmop]
papers_json = json.dumps(papers_mini, ensure_ascii=True)

lines = []
lines.append('export const meta = {')
lines.append("  name: 'hmop-remaining-extract',")
lines.append("  description: 'Batch extract HM+OP sampling data from remaining papers',")
lines.append("  phases: [{ title: 'Extract', detail: 'Agent reads paper.md, extracts HM+OP' }],")
lines.append('}')
lines.append('const RESULT = {type:"object",properties:{paper_id:{type:"string"},n:{type:"integer"},skip:{type:"string"}},required:["paper_id","n"]}')
lines.append("phase('Extract')")
lines.append('const P = ' + papers_json)
lines.append('const results = await pipeline(P, p => agent(')
lines.append('  "Read C:\\\\Users\\\\' + chr(26966) + '\\\\Desktop\\\\SRS\\\\outputs\\\\literature_mining\\\\_scripts\\\\agent_extract_prompt.md for rules. " +')
lines.append('  "Read G:\\\\' + chr(25991) + chr(29486) + chr(25972) + chr(29702) + '_\\u6700\\u7ec8\\\\" + p.stem + "\\\\parsed\\\\paper.md full text. " +')
lines.append('  "Extract real sampling-point HM(Cd/Pb/Cr/As/Hg/Cu/Zn/Ni mg/kg)+OP(Sum_PAH_ngg=16monomers sum,BaP_ngg,SumPCB_ngg,SumDDT_ngg,SumHCH_ngg,SumPBDE_ngg,TotalPHC_mgkg; ng/g). " +')
lines.append('  "Reject: stat rows(Mean/SD/Max/Min)/thresholds(Grade/GB)/risk(HQ/TEQ)/pot spiked/water/air/plant. " +')
lines.append('  "Output CSV(UTF-8-sig) C:\\\\Users\\\\' + chr(26966) + '\\\\Desktop\\\\SRS\\\\outputs\\\\literature_mining\\\\manual_extract\\\\hm_op\\\\" + p.paper_id + ".csv " +')
lines.append('  "Header: paper_id,sample_id,pollutant_std,value,unit,evidence_location,matrix,site_type,province,extract_notes. " +')
lines.append('  "sample_id=original(S1/A/B). HM=mg/kg OP=ng/g. extract_notes comma->quotes. " +')
lines.append('  "Remediation: find pre-remediation baseline not effect. " +')
lines.append('  "If no sample-level data, empty CSV+notes. Return paper_id,n,skip.",')
lines.append('  {label: p.paper_id, schema: RESULT}')
lines.append('))')
lines.append('const ok = results.filter(Boolean).filter(r => r.n > 0)')
lines.append('log("Done " + results.filter(Boolean).length + "/" + P.length + ", ok " + ok.length + ", samples " + ok.reduce((s,r)=>s+r.n,0))')
lines.append('return {total: results.filter(Boolean).length, success: ok.length, samples: ok.reduce((s,r)=>s+r.n,0)}')

script = "\n".join(lines)
# Clean control chars
script = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', script)

out = Path(r"C:\Users\曾鸿\Desktop\SRS\outputs\literature_mining\_scripts\wf_hmop_final.js")
out.write_text(script, encoding="utf-8")
print(f"Script: {out}, {len(papers_mini)} papers, {len(script)} chars")
