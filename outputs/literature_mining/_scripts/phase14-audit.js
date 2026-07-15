/** Phase14 数据质量抽样核查 Workflow
 *
 * 29 篇论文逐篇比对: CSV 提取结果 vs MinerU MD 原文
 * Paper data 通过 args 传入（沙箱无 fs）。
 */
export const meta = {
  name: 'phase14-audit',
  description: 'Phase14 自动提取数据质量抽样核查 — 29篇(9%), 1293行',
  phases: [
    { title: 'Audit', detail: '每篇论文独立核查3个维度' },
    { title: 'Synthesis', detail: '汇总 verdict, 统计错误率和类型' },
  ],
}

const AUDIT_PROMPT = `You are a data quality auditor. Verify whether Phase14's automated table extraction produced correct data for one paper.

For each data row, check 3 dimensions:
1. POLLUTANT MATCH: Does pollutant_std correctly identify what was measured?
2. VALUE ACCURACY: Is the value correctly extracted from the paper's table?
3. DATA QUALITY: Is this a real concentration measurement (not correlation, PCA, stats)?

Key red flags → DELETE these rows:
- source_caption mentions "correlation", "PCA", "Pearson", "factor loading", "相关矩阵", "主成分"
- HM values between -1 and 1 (mg/kg) → likely correlations
- Sample IDs named "Mean", "SD", "CV", "Min", "Max", "检出率" → statistics

Return JSON:
{"paper_id":"...","overall":"PASS|WARN|FAIL","total_rows":N,"keep_rows":N,"delete_rows":N,"issues":[{"row_idx":N,"dimension":"pollutant|value|quality","severity":"warn|fail","detail":"..."}],"summary":"..."}`

const VERDICT_SCHEMA = {
  type: 'object',
  properties: {
    paper_id: { type: 'string' },
    overall: { type: 'string', enum: ['PASS', 'WARN', 'FAIL'] },
    total_rows: { type: 'integer' },
    keep_rows: { type: 'integer' },
    delete_rows: { type: 'integer' },
    issues: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          row_idx: { type: 'integer' },
          dimension: { type: 'string', enum: ['pollutant', 'value', 'quality'] },
          severity: { type: 'string', enum: ['warn', 'fail'] },
          detail: { type: 'string' },
        },
        required: ['row_idx', 'dimension', 'severity', 'detail'],
      },
    },
    summary: { type: 'string' },
  },
  required: ['paper_id', 'overall', 'total_rows', 'keep_rows', 'delete_rows', 'summary'],
}

// args = array of {p, pool, n, csv: [{pollutant_std, value, unit, sample_id, evidence_location, source_caption, confidence}], md: "..."}
const papers = args

log(`Auditing ${papers.length} papers, ${papers.reduce((s, p) => s + p.n, 0)} total rows`)

// Phase 1: Audit
phase('Audit')
const results = await pipeline(
  papers,
  paper => {
    const csvPreview = paper.csv.map(r =>
      `  [${r.pollutant_std}] ${r.value} ${r.unit} | sample=${r.sample_id} | evidence=${r.evidence_location} | caption=${(r.source_caption||'').slice(0,120)}`
    ).join('\n')

    const prompt = `${AUDIT_PROMPT}

--- CSV ROWS (${paper.n} total, showing ${paper.csv.length}) ---
Paper: ${paper.p}  Pool: ${paper.pool}
${csvPreview}

--- MD TEXT (${(paper.md||'').length} chars) ---
${(paper.md||'').slice(0, 8000)}

Audit this paper now. Return JSON verdict.`

    return agent(prompt, {
      label: `audit:${paper.p}`,
      schema: VERDICT_SCHEMA,
      effort: 'medium',
    })
  }
)

const valid = results.filter(Boolean)
log(`Phase 1 done: ${valid.length}/${papers.length} valid verdicts`)

// Phase 2: Synthesis
phase('Synthesis')
const synthesis = await agent(`Analyze ${valid.length} audit verdicts from Phase14 automated extraction quality check.

Verdicts:
${JSON.stringify(valid.map(v => ({p:v.paper_id, overall:v.overall, total:v.total_rows, keep:v.keep_rows, delete:v.delete_rows, summary:v.summary})), null, 2)}

Detailed issues (top 20):
${JSON.stringify(valid.flatMap(v => (v.issues||[]).map(i => ({paper:v.paper_id, ...i}))).slice(0,20), null, 2)}

Produce a synthesis covering:
1. Pass/Warn/Fail % across all sampled papers
2. Error taxonomy (what types of errors, how common)
3. Estimated total data loss if we extrapolate to 314 papers
4. Root cause analysis — what in the pipeline caused these errors
5. Recommended fixes before merging Phase14 into training set
6. Should we merge? (true/false with reasoning)

Return JSON:
{
  "pass_rate": 0.XX, "warn_rate": 0.XX, "fail_rate": 0.XX,
  "total_sampled_rows": N, "estimated_total_loss": N,
  "error_taxonomy": [{"type":"...","count":N,"description":"..."}],
  "root_causes": ["..."],
  "recommended_fixes": ["..."],
  "should_merge": true/false,
  "executive_summary": "..."
}`, {
  label: 'synthesis',
  schema: {
    type: 'object',
    properties: {
      pass_rate: { type: 'number' }, warn_rate: { type: 'number' }, fail_rate: { type: 'number' },
      total_sampled_rows: { type: 'integer' }, estimated_total_loss: { type: 'integer' },
      error_taxonomy: { type: 'array' },
      root_causes: { type: 'array', items: { type: 'string' } },
      recommended_fixes: { type: 'array', items: { type: 'string' } },
      should_merge: { type: 'boolean' },
      executive_summary: { type: 'string' },
    },
    required: ['pass_rate', 'estimated_total_loss', 'error_taxonomy', 'root_causes', 'recommended_fixes', 'should_merge', 'executive_summary'],
  },
})

return { results: valid, synthesis }
