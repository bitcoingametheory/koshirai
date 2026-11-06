# Source-backed grouping and layout evidence

## Current native entry and clause release

The [current receipt](native_semantics_evaluation.json) preserves both counting
policies, fixed numerical acceptance, failed development passes, source hashes
and remaining errors. References are exposed provisional AI annotations. The
325-mention sword denominator and all 50 source/OCR hashes remain unchanged.

| Location policy | Version | Correct | Rejected | Missed | Precision | Recall |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Original area overlap | Previous default | 61 | 20 | 264 | 75.3% | 18.8% |
| Original area overlap | Current | 114 | 29 | 211 | 79.7% | 35.1% |
| Native line projection | Previous default | 64 | 17 | 261 | 79.0% | 19.7% |
| Native line projection | Current | 122 | 21 | 203 | 85.3% | 37.5% |

The original 80% precision target was **not met under the original location rule**.
The measurement repair was declared before rescoring. Numerical thresholds remain
at least 80 correct and 80% precision. Both versions pass through identical code;
no reference spelling, category, scope, source image or OCR was changed.

### Why location counting changed

The old check requires intersection area divided by the smaller box area to reach
0.5. On `ndl-1116200-0124`, the OCR line box `[2987,2022,3023,2199]` includes
`古刀上作`, while the shorter reference box `[2966,2013,3036,2101]` identifies
`古刀`. Their area score is only 0.4617 despite the correct printed occurrence.
This is a narrow whole-line box against a wider short annotation.

The optional `native_line_projection_v1` policy accepts the original check, or
at least 85% overlap of the smaller extent on **each axis**. The added rule applies
only to explicitly declared single native-line geometry. It does not apply to
multiline unions, unknown boxes, adjacent columns or nonoverlapping vertical spans.
Exact complete spelling and category plus one-to-one matching still govern the
sword count. Scored regions and unreadable exclusions still use the original rules.
Whole-line geometry still cannot verify character-level positions.

All eleven changed decisions across baseline and candidate were visually inspected
against the source scans; three are shared occurrences across versions. Their boxes
and old scores remain in the receipt. The repair does not turn every suspected
geometry error into a match. The original rule remains the evaluator default so
historical reports continue to reproduce exactly.

```sh
python3 -B benchmarks/compare_predictions.py \
  --baseline benchmarks/boundary_predictions.jsonl.gz \
  --candidate benchmarks/native_semantics_predictions.jsonl.gz \
  --references benchmarks/semantic_references.json \
  --output /external/native-legacy-comparison.json
python3 -B benchmarks/compare_predictions.py \
  --baseline benchmarks/boundary_predictions.jsonl.gz \
  --candidate benchmarks/native_semantics_predictions.jsonl.gz \
  --references benchmarks/semantic_references.json \
  --geometry-policy native_line_projection_v1 \
  --output /external/native-projection-comparison.json
```

The current native-clause set separately recovers 8 of 15 reviewed relationships
with zero extra claims and seven misses. This is a small closed-scope development
sample. Eight new bilingual mappings supplement ten grain mappings. The 37/37
lookup pilot and two withheld controls still pass. Fifteen entries across six fresh
private pages were inspected, including OCR failures that remain unresolved.
See [native semantics](../docs/native_semantics.md) for output contracts and the
prepared but unexecuted Astra/Sol comparison. No expert English accuracy is measured.

## Previous boundary release

The previous default added Japanese technical-term boundaries and ten cited
bilingual grain-pattern mappings. On the same 50 source images and raw OCR,
complete groups rise from 56 to 61, with rejections rising from 16 to 20.
Precision changes from 77.8% to 75.3%, and recall from 17.2% to 18.8%.
The separate private body-text pilot recovers cited English for 37/37 complete
targets, versus 1/37 previously, and withholds both nested negative controls.
These are exposed regression sets with provisional AI review, not independent
translation-accuracy scores. The 50-page reference has no scored English senses.

The [boundary receipt](boundary_evaluation.json) preserves the first failed pass
(62 groups and 25 rejections), the fixed acceptance thresholds, source/reference
hashes and remaining rejection locations. A four-category subtotal omits two
unmatched tradition predictions. The current comparison explicitly includes
`sword_tradition` alongside technical terms, smiths, schools and measurements,
reproducing the historical 56/16/269 baseline without changing references.

Reproduce the paired scores from the public frozen predictions:

```sh
python3 -B benchmarks/compare_predictions.py \
  --baseline benchmarks/bert_source_priority_predictions.jsonl.gz \
  --candidate benchmarks/boundary_predictions.jsonl.gz \
  --references benchmarks/semantic_references.json \
  --output /external/boundary-comparison.json
```

The comparator rejects changed source/OCR hashes, duplicate pages and incomplete
reference coverage. Live image runs still use `evaluate_semantics.py` below.
Saved private OCR and its page images remain outside this repository. The new
reader was checked on 13 retained pages and 860 lines, preserving raw text,
geometry, engine and separate corrected/ordered fields without OCR calls.

The comparisons below document earlier release snapshots.

The optional Jev integration has separate [evidence](jev_evaluation.json) and
[setup/replay instructions](../docs/jev_research.md). All approaches and failed
trials are summarized in [approaches tried](../docs/approaches.md).

The source-priority snapshot below is preserved unchanged. The new optional
BERT classifier has separate [training and evaluation evidence](../docs/bert_evaluation.md),
[complete results](bert_evaluation.json), and reproducible frozen predictions.
Its 50-page sword-group precision is 82.3% and recall is 15.7%.
The updated source-only comparison scores 77.8% and 17.2%, respectively.
Neither result establishes universal semantic accuracy.

Koshirai preserves literal OCR, identifies complete sequences, presents cited sword readings/meanings, and retains alternatives. The source-priority method uses documented source priority and explicit boundaries. Uncertain body-text matches remain candidates.

## Frozen source scope

The sample retains 50 Fujishiro frames from editions 1116191 and 1116200. Selection uses SHA256 of the frozen seed, edition and frame, without consulting predictions. These frames have now been used for development/regression. They are not a newly blind held-out test.

Every frame has one declared text region. References contain 1,589 mentions, including six disputed exclusions. Complete literal sequence plus overlapping source geometry defines a group. Category, reading and English are separate questions. Repeated positions count separately. An incomplete annotation never supplies exhaustive recall.

The references are source-only provisional AI annotations, without human expert adjudication. Original failures, reference hashes and counts remain in the historical evidence and local source receipts. No score is a probability.

## Measured complete sword groups

The following category-strict denominator contains 325 technical terms, smith/artisan names, schools and measurement expressions. A correct group must have both the complete printed sequence and the reference category.

| Method | Correct groups + categories | False groups | Misses | Precision | Recall |
| --- | ---: | ---: | ---: | ---: | ---: |
| General dictionary | 0 | 0 | 325 | unscored | 0.0% |
| Exact source matching | 137 | 176 | 188 | 43.8% | 42.2% |
| Source primary selections | 55 | 10 | 270 | 84.6% | 16.9% |

“False groups” means rejected under these matching rules, not independently established semantic errors. A source-image review found that four rejected sword outputs (雲生, 古刀, and two 新刀 occurrences) contain the reference term but fail the required geometry overlap. Other disagreements include category and character-form questions. The references and scores above remain unchanged pending documented adjudication. A failure can belong to extraction, localization, categorization, or the reference itself.

The general dictionary does not classify sword-domain categories. Its zero category-strict result does not mean it recognized no corresponding characters or names. The complete all-category spelling/geometry counts and matched coverage remain in the JSON report. General lookup recovers more total word groups; the primary selector favors precision and has lower recall. No universal OCR superiority is claimed.

## Image relationships

One source-selected illustration panel is annotated on each image-bearing right page. Three right pages contain no illustrations, and seven targets have unresolved continuation relationships. Forty entry/caption links have resolvable source anchors. These are target-panel measurements, not a whole-frame segmentation census.

All 50 scans completed. The detector located 41 of 47 annotated panels. The selector recovered 33 of 40 resolvable links, with 2 false links: 94.3% precision and 82.5% recall.

Entry markers, reading direction, running-head agreement and caption bands support layout inferences. A nearby image alone does not establish a relationship. All link proposals retain their evidence and uncertainty. Native groups and their individual images can share a caption; repeated correct panel/member edges are reported separately rather than counted as extra successes.

Inspect the [50-page overlay](../docs/evaluation.html) and [complete evaluation](semantic_evaluation.json) for successes and failures.

## Library evidence

The current the primary private reference source registry selects 376 reviewed page payloads. Every selected payload hash was verified. Migrated materialized path text is not used to bypass a saved hash. Paragraph readings and styles match the source-selected records.

The library adds short editorial English summaries through exact romanized the primary private reference glossary headwords and documented the supporting private reference kanji spellings. Both source chains, source hashes and locators remain attached. A homophonous personal name cannot acquire a technical definition through this join. These are factual source links, not expert certification of every library record.

Independent expert reading/English accuracy remains unmeasured. The source-example table shows actual raw OCR, dictionary candidates and cited sword selections. It supports inspection of retrieval behavior without inventing a translation-accuracy denominator.

## Reproduce

Use the repository installer and public sample instructions. The existing hash-verifying downloader accepts the source references as its cohort. Supply local image paths in an external copy of that manifest.

    python3 -B benchmarks/evaluate_semantics.py --manifest MANIFEST --config CONFIG --references benchmarks/semantic_references.json --output EMPTY_OUTPUT
    python3 -B benchmarks/evaluate_layout.py --predictions EMPTY_OUTPUT/predictions.jsonl --references benchmarks/semantic_references.json --output /external/layout.json

For scoring only, decompress semantic_predictions.jsonl.gz into an external predictions.jsonl and use the evaluator's --score-only option. No model call is needed. The source-priority method uses no trained semantic weights. The `bert` profile uses the separately documented trained classifier. Qwen, if used separately, is restricted to visible character strokes and shapes.
