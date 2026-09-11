# Assessment rubric and AAR

Assess the cooperative incident response, not flag collection. Apply the same
rubric to each cell's observed contributions and to the joint report; do not rank
cells against one another. Record evidence (ticket update ID and elapsed time).

| Dimension | Weight | Full-credit behavior | Partial / weak behavior |
|---|---:|---|---|
| Evidence and reproducibility | 25 | Accurate IDs/hashes, normalized time, repeatable query, preservation log | Findings plausible but uncited / incorrect normalization or invented evidence |
| Reasoning and scope | 25 | Separates facts/assessments/gaps, tests alternatives, revises after injects | Qualified but incomplete / certainty from absence or task-name matches |
| Timely command reporting | 20 | Initial and inject deadlines met with actionable uncertainty | Late but useful / silence until certainty or unsupported alarm |
| Collaboration | 15 | Useful cross-ticket evidence, named collection owners, reconciled disagreements | One-way sharing / isolated duplicate investigation |
| Defensive recommendations | 15 | Proportionate actions with impact, preservation, controller acknowledgment and verification | Correct action without tradeoffs / requests treated as completed containment |

For each dimension rate 0 (absent/unsafe), 1 (major coaching), 2 (partially correct),
3 (sound with minor gaps), or 4 (independent and well supported). Score = weight ×
rating / 4. Proposed coached proficiency is 70/100 with no fabricated evidence or
real-world action; the event owner confirms its use. Record hints separately to
guide future training. A well-justified “unknown” can earn full reasoning credit.

Observation sheet: cell, elapsed time, behavior, source/update ID, rubric dimension,
rating, coaching given, next practice. Use cell labels instead of personal names
in shared reports. Score report quality even if a technical tool failed; document
the limitation and whether an alternate format enabled the same reasoning.

## 25-minute AAR

Minutes 0–5: each cell gives one fact that changed its assessment and cites the source.
Minutes 5–10: reconstruct when command first received a credible warning; compare
actual reports with the decision deadlines. What was actionable before full certainty?
Minutes 10–15: reveal the canonical timeline and clock offset. Discuss v3 versus v4,
password reset versus revocation, denied roster access and WS-31's uncertainty.
Minutes 15–20: examine one cross-cell collaboration and one recommendation's tradeoff.
Minutes 20–25: assign three improvements with owners, rehearsal dates and observable
success criteria. Separate exercise design defects from participant learning needs.

Output template: observation / supporting ticket and time / why it mattered /
retain or change / owner / due date / evidence that improvement worked. Capture
unanswered questions, tool friction and inject timing adjustments. Keep individual
performance notes and exported participant work outside Git.
