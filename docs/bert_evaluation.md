# BERT context disambiguation

The `bert` profile adds a genuine Japanese BERT context encoder and a trained
role classifier. It separates supported smith, school, tradition, place, technical
term, measurement, person, clan, date, ordinary-language and unresolved categories.
It does not establish historical identity or settle every competing pronunciation.

| Input | Selected complete expression | Role |
| --- | --- | --- |
| ◇信房一文字 | 信房 / 一文字 | smith / school |
| 一文字派に属する刀工。 | 一文字派 | school |
| 一文字助真が鍛えた刀。 | 一文字助真 | smith |
| 備前伝の作風。 | 備前伝 | tradition |
| 備前国に住む。 | 備前 | place |
| 刀工兼元が打った刀。 | 兼元 | smith |
| 兼元派に学んだ鍛冶。 | 兼元派 | school |

These are reproducible integration examples. They are not an independent expert
translation test. Names, role evidence, source spelling and original OCR remain
separate. A complete cited smith name owns its nested school prefix and given name.

## What runs

The encoder is [Tohoku NLP's character-based Japanese BERT v3](https://huggingface.co/tohoku-nlp/bert-base-japanese-char-v3),
pinned to `ccddee593a9e03a589ae1feedcd4d1eb06d6ba02`. Inference verifies local
encoder files and the packaged classifier head. It does not download models.
The encoder stays frozen. A trained linear head uses the contextual CLS vector,
target-span mean and surrounding-context mean: 2,304 input features.

The head predicts a role distribution. Selection requires a top model score of
at least 0.65, a margin of 0.15, and an existing supported candidate for that role.
Unsupported or uncertain choices abstain. Source priority orders candidates within
the chosen role. Competing readings and English senses remain visible through
`sense_state` and alternatives. Printed quantities with units use their deterministic
measurement interpretation. Scores are not calibrated correctness probabilities.

The semantic library also gains 51 cited assertions: school/tradition mappings and
four complete personal names. Explicit the primary private reference headings support the main mappings.
Bare Ichimonji and Ohara additionally require a literal/romanized source bridge.
Suffix groups retain their printed stem and derivation without inventing readings.
All selected the primary private reference payload hashes are checked during rebuilding. These source
facts are retrieval evidence, not classifier training labels.

## Training and observed limits

The frozen [training data](../benchmarks/bert_training.json.gz) contains recovered
native OCR contexts paired with provisional source-only AI role annotations.
Original scans and references come from the existing public-domain Fujishiro cohort.
Source pages are split by a fixed hash into training, validation and test partitions.
Identical source contexts crossing partitions are excluded. Synthetic teaching
examples have separately identified origins and template splits. Artificial heading
combinations teach grammar and assert no historical relationships.

Training uses seed 106. Validation macro accuracy selects epoch 30. Test observations
from earlier trials informed development, so these partitions now provide regression
evidence. They are not a fresh blind test. Pretraining exposure is unaudited.

The raw role classifier matches 169 of 178 source test annotations, or 94.9%.
That result is conditional on supplying an already recovered target and its location.
It is not OCR, term-boundary, translation, or complete-page accuracy. Ordinary-language
examples account for 112 of those 178 targets. School recognition remains weak:
2 of 4 source test school labels match. There are no source tradition test labels.
Synthetic tradition tests match 10 of 10; synthetic school tests match 14 of 28.
No human expert labels or independent English-meaning accuracy measurements exist.

On those same 178 recovered targets, evidence-constrained BERT selects 131 roles:
130 match and 1 disagrees, with 47 abstentions. Source priority selects 58:
43 match and 15 disagree, with 120 abstentions. The methods cover different subsets.
Their 99.2% and 74.1% selection precision must not be described as complete-system accuracy.

An attention-adapter experiment failed to improve validation macro accuracy.
Its negative results remain in the local research receipts. The shipped implementation
uses the smaller frozen-encoder method; it contains no unused adapter execution path.

## End-to-end 50-page comparison

All 50 original scans completed. Original reference text, geometry matching and
categories remain unchanged. Complete sword-group results include technical terms,
smiths, schools, traditions and measurements in the declared regions.

| Method | Matches | Rejections | Misses | Precision | Recall |
| --- | ---: | ---: | ---: | ---: | ---: |
| Original source-priority release | 55 | 10 | 270 | 84.6% | 16.9% |
| Updated library, source priority | 56 | 16 | 269 | 77.8% | 17.2% |
| Updated library, BERT | 51 | 11 | 274 | 82.3% | 15.7% |

BERT is more selective than the updated source-only method. It rejects more wrong
selections and misses additional valid terms. It does not beat the original release
on every measure. The default source-priority profile remains available, and BERT
must be explicitly selected. No universal OCR or semantic superiority is claimed.

Rejection is a benchmark outcome, not expert proof of a false meaning. Some correct
visible terms fail the original geometry rule or character-form comparison. Neither
reference disagreements nor genuine classifier mistakes are erased. Review the
[full report](../benchmarks/bert_evaluation.json), including per-page errors and
per-category confusion. The original release evidence remains unchanged. Public prediction exports omit
only machine-local `source_fields.crop` cache paths. Source hashes, text, geometry,
candidates and decisions remain intact. Recomputed scores equal the original scores.

Layout recovers 33 of 40 resolvable image links, with 2 rejected links: 94.3% precision
and 82.5% recall. It locates 41 of 47 target panels. These remain layout proposals,
independent of the BERT classifier. This is target-panel evidence, not a whole-frame census.

The installed-package CPU trial passes with real encoder inference. Dependencies
were reused in that trial; it is not evidence of a fresh dependency installation.
All 76 behavior tests pass with BERT integration enabled. A separate training run
with fresh feature extraction reproduced the exact classifier parameter hash on
the same host. This does not establish bit-identical training across other hardware.

## Reproduce

Install with `sh setup.sh --install-ocr --install-bert`. Select
`scan --semantic-profile bert`. See the [researcher guide](researcher_guide.md) for
CPU/GPU configuration and external data paths.

Train from the public frozen data and a verified encoder:

```sh
python3 -B benchmarks/train_bert.py --dataset benchmarks/bert_training.json.gz \
  --base /external/bert --output /external/reproduced-training --device cpu
```

The output contains the head, hashes, split metrics and decisions. Compare candidates
with `benchmarks/evaluate_bert.py`. Reproduce page scoring by decompressing
`bert_predictions.jsonl.gz` or `bert_source_priority_predictions.jsonl.gz` into an
external `predictions.jsonl`, then use `evaluate_semantics.py --score-only` with the
original references and a manifest carrying the same page identifiers.

[Jev research](jev_research.md) describes the subsequently implemented hosted decision option. Jev is excluded
from this historical BERT measurement and has its own report.
