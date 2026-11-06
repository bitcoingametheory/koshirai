# Approaches tried and final release

Koshirai combines literal OCR, page relationships, a derived sword library and
reviewable semantic proposals. The final release retains useful comparisons rather
than presenting one score as proof that every term is understood.

## What was tried

| Approach | Outcome | Release status |
| --- | --- | --- |
| General dictionary lookup | Useful general meanings; cannot itself distinguish every sword role or complete name. | Lexical comparison retained. |
| Exact source matching | Retrieves attested expressions; source inclusion alone can confuse a smith with a school. | `exact` comparison retained. |
| Source-priority selection | Uses complete boundaries, source evidence and explicit categories. Conservative image-text selections reduce coverage. | Default `contextual` profile. |
| Earlier custom feature/weighted rankers | Did not establish the required general semantic accuracy. | Executable rankers retired; historical evaluation evidence retained. |
| Frozen Japanese BERT plus trained linear role head | Uses surrounding text to select supported roles. Reproducible parameters and real CPU inference verified. Short headings and rare roles still cause errors. | Optional `bert` profile. |
| Attention residual adapters | Did not improve validation macro accuracy over the frozen encoder. | Experiment retained privately; unused adapter code is excluded. |
| Jev candidate-only choice | Combined role and reading ambiguity into one distribution. It abstained on the tested terse heading. | Superseded by the separated questions. |
| Jev role choice, candidate choice and support judgment | Keeps role certainty separate from pronunciation certainty. Closed-set validation prevents invented candidates. More conservative than BERT in this trial. | Optional `jev` profile, live or offline replay. |

Qwen vision has a separate, restricted character-stroke review role. It is not the
semantic judge and does not run automatically in these scan profiles. NDLOCR-Lite
supplies literal characters and native regions. Layout rules select entry/caption
relationships independently of the semantic classifier.

## Current native entry and clause release

The current release adds explicit entry/name structure, eight bilingual temper-pattern
mappings and bounded native Japanese relations. The full [native semantics account](native_semantics.md)
records fifteen entry cases and the clause result: eight correct, zero extra and
seven missed relationships across twelve reviewed lines. Frontier comparison inputs
and a bounded runner are ready; Astra/Sol live evaluation is pending.

Four development passes failed the original 80% precision target. The final original
area score is 114 correct, 29 rejected and 211 missed (79.7% precision). Source-image
review confirmed a box-shape counting defect already noted in the prior evaluation.
With the explicit native-line projection repair applied to both versions, the paired
counts are 64/17/261 before and 122/21/203 after (85.3% final precision).
Both counting policies, failed passes and unchanged reference hash remain in the
[new receipt](../benchmarks/native_semantics_evaluation.json). This is exposed
regression evidence; no score establishes expert translation quality.

## Previous boundary release on the same 50-page cohort

The previous boundary repair recovered 61 complete groups with 20 rejections and
264 misses: 75.3% precision and 18.8% recall. The paired previous default recovers
56, with 16 rejections and 269 misses. This is a coverage gain with a precision
cost, not a universal improvement. Source images and raw OCR hashes match on all
50 pages. No new OCR or hosted model call was needed for this comparison.

The first boundary pass failed the declared 75% precision threshold. It admitted
calendar words as smiths through broader punctuation rules and treated a noun
plus a particle as an inflection. The repair restores conservative name boundaries
and narrows the technical boundary cue. Failed counts remain in the
[boundary evidence](../benchmarks/boundary_evaluation.json).

Ten image-reviewed bilingual grain-pattern mappings also repair missing English
glosses. In the private retained-OCR regression, mappings alone still selected
only 1/37 complete body-text occurrences. With the boundary repair, the parser
selects 37/37 and withholds both smaller terms inside unmapped size compounds.
These occurrences were purposively retrieved and already inspected. They do not
measure blind recall, OCR character accuracy, or independent expert translation.
The two editions are witnesses to one work, not independent corroboration.

For example, public frame `ndl-1116191-0071` contains `丁子足長く入る` and
`鋩子は小丸`. The parser now selects the complete `丁子足` and `小丸` spans,
with the cited meanings “clove-shaped temper legs” and “small rounded tip return.”
Their PrimaryReference glossary citations are printed pages 337 and 342,
locators `i358_glossary_line_035` and `i363_glossary_line_037`. The raw OCR stays
unchanged. The same frame's `彫物を以て` now yields “blade carving,” with its
page 339 glossary citation. Full source hashes and alternatives accompany each
selection in the frozen predictions.

Remaining new benchmark rejections include `代作` on `ndl-1116191-0083`, and
`太刀` and `刄文` on `ndl-1116200-0051`. The reference requires the complete
literal, category and location to agree. A supported dictionary meaning alone
does not make these benchmark selections correct. All 20 rejections and 264
misses remain in the comparison; no reference was changed to improve the score.

The older comparisons below remain historical evidence. Their executable optional
profiles retain their own behavior and limitations.

The same public-domain original pages, native OCR and provisional reference rules
support these complete sword-group comparisons. They concern declared text regions,
not every expression in every frame. Category, spelling and geometry must match.

| Method | Matches | Rejections | Misses | Precision | Recall |
| --- | ---: | ---: | ---: | ---: | ---: |
| Original source-priority snapshot | 55 | 10 | 270 | 84.6% | 16.9% |
| Updated derived library, source priority | 56 | 16 | 269 | 77.8% | 17.2% |
| BERT | 51 | 11 | 274 | 82.3% | 15.7% |
| Jev | 30 | 4 | 295 | 88.2% | 9.2% |

Jev's higher selection precision comes with lower recall. The original source-only
snapshot also outperforms later methods on some measures. No universal improvement
is claimed. Benchmark rejections include location and spelling-form disagreements;
they are not automatically established false meanings. References are provisional
AI annotations. These exposed pages are development/regression evidence.

On 178 already recovered targets, source priority selects 58 with 43 matches,
BERT selects 131 with 130 matches, and Jev selects 106 with 100 matches. That is
conditional role selection with different abstention rates, not end-to-end OCR accuracy.
Independent expert English-meaning accuracy remains unmeasured.

## Private inputs and sanitized public releases

The owner reports that the private Japanese–English sword references were legally
purchased. Their identities use pseudonymous source labels in this public release.
Derived facts retain opaque provenance hashes and locators. Required dictionary,
Unicode, character-data and software license attribution remains intact.

The derived library is separate from trained neural parameters. The shipped BERT
head was trained on public OCR annotations and synthetic teaching examples.
The hosted Jev model's pretraining is controlled by its provider. Neither fact is
relabelled as completed private-data neural training.

The improvement workflow is designed to train and evaluate locally on permitted
private data, then publish sanitized derived libraries and model parameters that
protect the original data holders' intellectual property. Private originals,
full source paragraphs and raw reference scans stay outside the public repository.
Future private training must retain private provenance and publish an accurate
training manifest without releasing protected inputs. Source sanitization is a
release requirement, not a claim of blanket legal clearance.

The retained JPEGs are the separately authorized public-domain benchmark samples,
with their original attribution and hashes. They are not private reference books.
API credentials and local environment files are excluded. Jev receives bounded
public OCR context and short derived candidates, not full private source passages.

See [BERT evidence](bert_evaluation.md), [Jev evidence and replay](jev_research.md),
the [complete Jev report](../benchmarks/jev_evaluation.json), and
[third-party notices](notices/third_party_data.md).
