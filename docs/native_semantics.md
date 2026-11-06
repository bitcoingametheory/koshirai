# Native Japanese interpretation

Koshirai keeps the Japanese source as the interpretation record. English is a
presentation of supported readings, meanings and bounded relations. Translating
an OCR page into English first would discard distinctions needed for exact term
boundaries, historical spellings and source citations.

## Current behavior

`entry_structure.py` reads printed entry marks, index tabs and bracketed fields.
A complete attested heading or matching printed index can support a name boundary.
There is no generic two-character name split. Era and province fields stay distinct
from smith names. Qualifiers and same-name historical identities can remain unresolved.
Primary and alternate saved OCR passes are separate witnesses; neither silently
rewrites the other. Entry parsing follows patterns inspected in the private library,
with explicit offsets and evidence added for the public application's contract.

`japanese_clauses.py` recognizes a small set of native constructions: mixture,
description, resemblance, presence/absence, parent/child, teacher/student and relative
frequency. Each proposal contains original argument and predicate spans, polarity,
modality, supporting term citations and a clause ID. Conditional constructions,
quotations and unsupported negation scopes abstain. Remaining wording stays visible.
This is a bounded grammar, not complete Japanese semantic parsing.

`results.jsonl` exposes these records in `japanese_interpretations`.
`interpretations.jsonl` makes the same units convenient to inspect after a folder
scan. English remains null when an argument lacks a supported gloss or reading.
Even a populated English field is a rule proposal, not an accepted translation.
For example, the synthetic control `小沸が見られない。` preserves negative polarity.
The double-negative control `小沸がないこともない。` stays unresolved.

A narrowly overlapping duplicate OCR detection can share one primary mention;
its original witness remains attached. Repeated same-term occurrences inside one
native region are kept separate because whole-line geometry cannot align them safely.
Dictionary romanization now selects a named scheme, so cache serialization cannot
silently change a long vowel.

## Added source facts and evaluated limits

Eight additional bilingual facts cover `広直刃`, `中直刃`, `細直刃`, `互の目`,
`互の目乱れ`, `片落ち互の目`, `三本杉` and `互の目丁子`. These extend the ten grain
mappings. Japanese and English page locators, hashes and review status accompany
each bounded fact. Related editions are not independent witnesses to historical truth.

The [release receipt](../benchmarks/native_semantics_evaluation.json) records:

- Fifteen image-reviewed entry cases on six fresh private pages. Eleven reference
  names have recoverable primary heading boundaries. Four cases require abstention
  or further character/structure review. This is an inspected development sample.
- Twelve native OCR lines with fifteen reference relationships in the closed relation
  scope. Eight were recovered, none were added incorrectly against those references,
  and seven were missed. Richer descriptions are outside that denominator.
- The earlier pilot's 37/37 complete-term English selections and two withheld nested
  controls remain intact. This measures selected lookup occurrences, not English accuracy.
- Five installed public scans, 336 idempotently imported observations, ten independent
  workflow smoke frames and 135 passing tests. Eleven optional BERT integrations were skipped.

Private images and prose remain outside the release. Reviews are provisional AI
source-image checks. No human-expert English accuracy or general OCR error rate is claimed.
The [benchmark guide](../benchmarks/README.md) explains the frozen50 counting repair
and preserves the original failed threshold result.

## Which model belongs where

Use saved OCR when its relevant complete spellings survive. Inspect image crops
when strokes, missing characters or reading order are uncertain. More OCR cannot
repair a semantic boundary rule. Qwen is limited to that character inspection role.

BERT and Jev can help rank supported roles and meanings. They do not establish
historical identities. A frontier model can propose clause relationships and a final
English rendering, but must be measured on identical Japanese evidence before it
replaces the local method. Neither Astra nor Sol has a demonstrated win in this release.

## Optional paired frontier experiment

`benchmarks/evaluate_frontier.py` prepares and runs the same bounded inputs through
`gpt-6-astra` and `gpt-6.1-sol`. It is separate from ordinary parsing. Twelve private
cases were prepared; the live comparison is pending a configured API credential.
No model calls or model accuracy scores are represented as completed.

Create an external JSON list of cases. Each case needs a unique `id`, native `text`
(up to 1,200 codepoints), and `source.source_sha256`. For evaluation, provide
`reference_mentions` with literal/start/end/category, and `reference_claims` with
relation, argument spans, polarity and modality. Freeze those references before
looking at model output. Review whether the passages may be sent to the provider.

```sh
python3 -B benchmarks/evaluate_frontier.py prepare \
  --cases /external/cases.json --prepared /external/prepared.json \
  --output /external/plan.json
```

Inspect the prepared text, candidate senses and cost reservation. Configure
`OPENAI_API_KEY` in the environment. The example below allows at most 24 calls
and an $8 conservative reservation, not a claimed bill:

```sh
python3 -B benchmarks/evaluate_frontier.py run \
  --cases /external/cases.json --prepared /external/prepared.json \
  --output /external/model-results --max-calls 24 --max-cost-usd 8
python3 -B benchmarks/evaluate_frontier.py score \
  --cases /external/cases.json --prepared /external/prepared.json \
  --output /external/model-results
```

Prepared inputs omit reference answers and selector scores. Both models receive
identical Japanese text, source choices and instructions. Responses use strict JSON
with closed candidate IDs. Validation checks exact offsets, nonoverlap, argument
categories and clause boundaries. It cannot establish semantic or English truth.
An English review queue remains explicitly unscored until independently reviewed.

Requests use medium reasoning and 4,096 output tokens by default. The runner records
attempts before transmission, verifies replay hashes and does not retry existing
receipts automatically. Unknown usage stays unknown after a failed request. The
cost reservation uses pinned rates documented in the runner; check current pricing
before a later run. Missing or failed responses remain misses in the comparison.
The supplied API is called with `store=false`; this is not a claim of zero provider
retention under every account policy.
