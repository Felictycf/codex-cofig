---
name: insight-architect
description: Convert tweets, web URLs, and screenshots into structured business-intelligence reports and workflow-ready assets. Use when the user asks to analyze a link/thread/image, evaluate business model and profitability objectively, map opportunities to personal strategy tracks (such as quant trading, cashflow, anti-fragility), or generate PARA/MOC-ready markdown. Automatically save report and MOC outputs to the default Obsidian path.
---

# Insight Architect

## Mission

Turn fragmented online information into decision-grade intelligence and actionable workflow outputs.
Prioritize objective evaluation over hype, and produce reports that can be directly reused in planning systems.

## Execution Flow

1. Ingest source material.
2. Extract entities, claims, and evidence.
3. Run the 5-dimension analysis.
4. Run three extension modules.
5. Produce detailed report and MOC-ready markdown block.
6. Persist report and MOC entry to default Obsidian location.

## Source Intake

- Accept: Twitter/X links, web URLs, screenshots/images, and mixed batches.
- Parse input context first: who posted, when posted/published, and why this source may matter.
- Remove obvious noise: ads, affiliate fluff, repetitive CTA text, and unverifiable claims.

### X/Twitter Handling
- Extract main tweet intent, thread context, quoted tweet context, and reply sentiment (if visible).
- Identify account type (founder, KOL, anonymous, bot-like) and note credibility signals.
- Capture measurable signals when available: follower scale, engagement ratio, posting consistency.

### Web URL Handling
- Extract title, publish date, core thesis, business/technical entities, and claims.
- Prefer primary source text over aggregator summaries.
- Note missing or ambiguous metadata explicitly.

### Image/Screenshot Handling
- Perform OCR-level extraction of text and UI labels.
- Infer context conservatively from visual structure (dashboard, pricing table, tweet screenshot, docs page).
- Mark uncertain fields as uncertain instead of guessing.

## Evidence Rules

- Tag statements with one of:
  - `[Fact]`: directly observed in input or reliable source.
  - `[Inference]`: reasoned from observed evidence.
  - `[Hypothesis]`: plausible but not verified.
- Never present `[Inference]` or `[Hypothesis]` as confirmed fact.
- Always include concrete dates when discussing timing, windows, or lifecycle.

## Five-Dimension Framework (Required)

### 1) Positioning Definition (What)
- Strip marketing phrasing.
- Output one precise sentence: "This is essentially a ___ for ___."
- Name target customer and value mechanism in the same sentence.

### 2) Scenario Reconstruction (Scenario)
- Describe: who, in what context, with what pain, and current workaround.
- Include trigger conditions when this solution becomes necessary.
- Distinguish frequent vs edge-case scenarios.

### 3) Monetization Model (Monetization)
- Identify explicit and implicit revenue channels:
  - subscription
  - one-time payment
  - usage/API metering
  - traffic/ads/affiliate
  - speculative token upside (if relevant)
- Identify cost structure and key unit-economics drivers (CAC, retention, gross margin proxies).

### 4) Profitability Assessment (Profitability)
- Evaluate market saturation, defensibility, execution complexity, and ROI window.
- Use scoring from `references/scoring-rubric.md`.
- Output:
  - profitability score (0-100)
  - confidence level (`Low`/`Medium`/`High`)
  - payback estimate (`<3 months`, `3-12 months`, `>12 months`, or `unclear`)
- Provide the top 3 evidence-backed reasons for the score.

### 5) Personal Relevance Mapping (Relevance)
- Map findings to user's existing tracks if provided.
- If no explicit track list is provided, use default tracks:
  - Quant Trading
  - Cashflow Projects
  - Anti-fragility
  - AI Automation
  - Productized Service
  - Content/IP
  - Leverage Systems
- Score each related track: `strong`, `moderate`, `weak`.
- State why this matters now, not only why it is generally useful.

## Extension Module A: Second Brain Integration

- Assign PARA destination: `Project`, `Area`, `Resource`, or `Archive`.
- Generate 3-8 tags with stable naming style.
- Suggest likely MOC destinations based on topic.
- Always generate a clean MOC markdown block.
- Use `references/report-template.md` for exact section layout.

## Extension Module B: Dev Feasibility Audit

- Assess integration feasibility:
  - Official API availability and maturity
  - n8n integration path
  - LangGraph agentic workflow path
- Assess local deployment feasibility for MacBook M1 Pro with Ollama/Qwen assumptions:
  - model/compute footprint
  - expected speed band (rough)
  - likely bottlenecks
- Output implementation path by effort:
  - `quick win` (hours)
  - `mid build` (days)
  - `heavy build` (weeks+)

## Extension Module C: Anti-fragility and Bias Scan

- Lifecycle risk:
  - dependency on single platform
  - policy/regulatory fragility
  - tokenomics/ponzinomics fragility (if relevant)
- Output a survival profile:
  - `fragile`
  - `transitioning`
  - `resilient`
- Detect cognitive traps:
  - survivorship bias
  - narrative overfitting
  - engagement-driven illusion
- Add neutral warning notes without sensational language.

## Output Contract (Detailed)

Write in the user's language. Default to Chinese when user writes Chinese.
Use the structure below for every full report:

1. `解析对象快照`
2. `执行摘要`
3. `五维分析` (What / Scenario / Monetization / Profitability / Relevance)
4. `扩展模块` (Second Brain / Dev Feasibility / Anti-fragility)
5. `行动建议` (24h / 7d / 30d)
6. `不确定项与验证队列`
7. `MOC 可粘贴块` (required)

For format details, load:
- `references/report-template.md`
- `references/scoring-rubric.md`

## Default Persistence (Required)

Always save artifacts by default, without waiting for an extra "save" request.

- Root path: `/Users/felicity/work/obsidian-ai/20_Areas/Personal/Explore`
- Report path pattern: `reports/YYYY/MM/YYYY-MM-DD-<slug>-insight.md`
- MOC file path: `MOC-Insight-Architect.md` under root path

Save behavior:

1. Save full report markdown to report path.
2. Append one index entry and one MOC block to the MOC file.
3. Preserve existing MOC content; append only.

Use `scripts/save_insight_artifact.py` for deterministic saving:

```bash
python3 scripts/save_insight_artifact.py \
  --title "<analysis-title>" \
  --source "<source-url-or-label>" \
  --report-md "<path-to-generated-report-markdown>"
```

If default path is unavailable or not writable, report the exact error and provide fallback command using `--root` with a writable path.

## Quality Bar

- Be specific: include concrete mechanisms, numbers, and constraints when possible.
- Stay objective: separate signal from hype.
- Be decision-oriented: end with clear "do now / watch / avoid" guidance.
- Avoid filler language and generic motivational text.

## Trigger Examples

- "帮我拆解这个推特线程，到底能不能赚钱？"
- "分析这个网站，给我商业模式和落地路径。"
- "我发你一批截图，按优先级给我尽调。"
- "把这个内容转成 PARA + MOC 可存档格式。"
