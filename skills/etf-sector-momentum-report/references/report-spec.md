# ETF Sector Momentum Report Spec

## Scope

This skill turns a sector-grouped ETF watchlist into a trading report with separate short-term, mid-term, and long-term conclusions.

## Sector Metrics

For each sector, aggregate the ETFs beneath it and compute:

- `avg_rank`
- `avg_rel5`
- `avg_rel20`
- `avg_rel60`
- `avg_rel120`
- `avg_1d`
- `avg_r20`
- `avg_r60`
- `avg_r120`
- `consistency`
  - Share of ETFs with `Rank >= 60` or `REL20 >= 0`

## Short-Term Score

Use a weighted score on a `0-100` scale:

- `30% avg_rank`
- `25% scaled avg_rel5`
- `20% scaled avg_rel20`
- `15% scaled avg_1d`
- `10% consistency`

Scale percentages before combining so that sectors remain comparable.

## Three-Day Score

Use the most recent up to `3` daily snapshots:

- Weighted average of the current and previous short-term scores
- Small bonus for improving slope
- Small penalty for deteriorating slope

If there is only one snapshot, use the current score and label the result as provisional.

The final short-term score must directly include a recent-3-day trend component rather than using 3-day history only at the conclusion layer.

## Mid-Term Score

Use:

- `30% avg_r20`
- `25% avg_r60`
- `20% scaled avg_rel20`
- `15% scaled avg_rel60`
- `10% consistency`

## Long-Term Score

Use:

- `30% avg_r60`
- `30% avg_r120`
- `15% scaled avg_rel60`
- `15% scaled avg_rel120`
- `10% consistency`

Long-term means `60-120` day structure. YTD can be shown as a side reference but should not replace the long-term score.

## Conclusion Heuristics

- `短线结论`: derive from the final short-term score and emit one of `强势 / 偏强 / 震荡 / 偏弱 / 弱势`
- `中期结论`: derive from the mid-term score and emit one of `强势 / 偏强 / 震荡 / 偏弱 / 弱势`
- `长期结论`: derive from the long-term score and emit one of `强势 / 偏强 / 震荡 / 偏弱 / 弱势`
- `交易结论`: derive from the combination of short-term, mid-term, and long-term conclusions

## Report Sections

### 首页结论

Summarize:

- strongest sector today
- strongest sector over the last three days
- strongest sector in the mid-term
- strongest sector in the long-term
- current main direction
- avoid list

### 板块强弱总表

Include:

- ranking
- sector
- short-term score
- three-day score
- short-term conclusion
- mid-term conclusion
- long-term conclusion
- trading conclusion

### 最强板块拆解

Cover the deduplicated set of:

- short-term leader
- mid-term leader
- long-term leader

and explain:

- why the sector is strong in the short term
- whether the middle trend supports it
- whether the long trend supports it
- how to trade it over `1-3` days
- what invalidates the view

### 最弱板块拆解

Cover the weakest `2-3` sectors and explain why they should be avoided.

### 未来1-3天推演

Always include three scenarios:

- 延续
- 分化
- 退潮

### 执行摘要

Finish with:

- 最值得交易
- 次优方向
- 观察名单
- 回避名单
