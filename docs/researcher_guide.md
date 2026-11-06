# API and local research

`kanji-translator scan INPUT --output OUTPUT` accepts a local image/PDF folder.
The output must be empty and outside the input and checkout. Files sort naturally;
PDF pages and multi-frame TIFF frames retain order. `--max-pages N` bounds a run.
No private source is fetched or uploaded. Python 3.12+, pip/venv, HTTPS and enough
external disk space are prerequisites; setup makes no OS/driver changes.

`sh setup.sh --install-ocr` installs the application, current public dictionary
snapshots and pinned CPU NDLOCR-Lite in external environments. Use `--source-dir`
for complete offline dictionary gzip files. `--update` refreshes dictionary
snapshots; hashes and source releases identify the installed dictionaries.
Source-evidence selection needs neither a GPU nor cloud calls.

`KANJI_DATA_DIR` defaults to the user data home plus `kanji-translator`.
`KANJI_CACHE_DIR`, `KANJI_ENV_DIR`, `KANJI_LEXICON` and `NDLOCR_PYTHON` explicitly
override cache, application environment, dictionary DB and OCR Python locations.
An external JSON file passed to `scan --config` can set:

```json
{
  "ocr_config": {"ndl_python": "/external/ndlocr/environment/bin/python", "timeout": 120},
  "image_config": {"orientation": "vertical"},
  "semantic_config": {"profile": "contextual"}
}
```

Orientation is a layout hint; native individual lines retain horizontal/vertical
orientation. NDLOCR text blocks constrain continuation. Vertical columns read
characters top to bottom and columns right to left; horizontal exceptions stay
separate. Titles/captions/furniture constrain blocks. Missing chapters and uncertain
figure relationships remain explicit unknowns/candidates, including isolated scans.
The native detector proposes figure blocks; geometry alone does not verify links.

`results.jsonl` contains source hashes, page/region IDs, native OCR, layout and
selected `semantic_mentions`. Each mention retains literal offsets, line geometry,
category, selected reading/English/name, actual source support, alternatives,
model version and uncertainty. Geometry is a whole OCR line unless explicitly
aligned to multiple lines; no character boxes are fabricated. Names have name
readings, never character-by-character English. Unsupported English stays null.
Scores are uncalibrated candidate margins. Specific identities remain unaccepted.

`raw_ndl.txt` preserves native transcripts; `text.txt` shows the working literal
transcript, including explicitly source-reviewed corrections. `terms.jsonl`
contains selected mentions. `interpretations.jsonl` contains native entry fields,
clause spans, relationship proposals, polarity, uncertainty and supported English
summaries. See [native semantics](native_semantics.md) for scope and model experiments.
`unresolved.jsonl` and `summary.json` expose failed
pages, unreadable regions and unknown lexical offsets. Successful execution does
not establish semantic or OCR accuracy. `text.txt` is the single working-text
export; there is no automatic character rewriting.

The JSON CLI also supports `parse`, `lookup`, `candidates`, `read-retained`,
`export-reviewed`, `record-review`, `corpus-ingest`, `corpus-inspect` and
`corpus-review`. Supply JSON on stdin or `--request FILE`. File parsing requires
`path` plus matching `sha256`; text uses `{"kind":"text","text":"雲次"}`.
`parse` is also importable from `kanji_translator`. HTML readers accept saved
content without network access. Retained private integrations require an explicit
trusted `module:function` adapter; private paths are never guessed.

For a saved library export, use `parse` with `kind="library_ocr"`, its file `path`
and SHA-256, an explicit `source_id`, and a one-based PDF `page`. The JSON export
contains `source` (including `id` and original PDF `sha256`) and `pages`. Each page
contains `source_id`, `page`, `text_raw`, `engine`, and native `lines` with `t`
(literal text), `b` (four polygon points), and optional `v` and `c` fields.

```json
{
  "kind": "library_ocr",
  "path": "/external/library-snapshot.json",
  "sha256": "REPLACE_WITH_SNAPSHOT_SHA256",
  "source_id": 7,
  "page": 2,
  "semantic_config": {"profile": "contextual"}
}
```

This route performs no OCR. It preserves the exact `text_raw` string, including
terminal newlines, in `raw_ndl_transcript`. Original page fields, corrected text,
ordered text and line order remain in `native_payload.page`. Semantic selections
use individual raw lines. Separate lines are never joined by this reader.
Line identities retain the snapshot hash, original PDF hash, PDF/printed pages,
engine, original polygon and native line index. Coordinates belong to the saved
render and are not transferred between editions. The reader makes no server calls.

Each contextual candidate's `boundary` explains selection or withholding. Cited
multi-character technical terms can be bounded by Japanese kana, adjacent cited
terms or a possible following inflection. Attested longer technical expressions
own their components. An unmapped size compound keeps the smaller match visible
as a candidate with `complete_candidate`, without assigning its English to the
whole compound. Names use exact attested boundaries, explicit entry structure, generation/name
labels and bounded Japanese particle cues. Ambiguous person/school roles stay unresolved.

Library maintainers can pass `--aligned-terms EXTERNAL_JSONL` to
`python -m kanji_translator.build_sword_library` alongside its normal build inputs.
The exporter requires exact complete labels, source-image review status, hashes
and separate edition/page locators. It exports only bounded lexical facts, never
private passages or image files. The source review remains explicitly provisional.

`lexical_config` supports a read-only dictionary `path`, morphology `profile` and
`enabled`. Exact bounded dictionary matching works without morphology. Modern
morphology uses pinned MeCab/UniDic. Historical optional dictionary profiles live
in the external `profiles.json`. Normalization preserves literal spelling and
records retrieval variants; semantic similarity never supplies missing strokes.

`semantic_config.profile="exact"` selects the fixed library comparison.
The default `contextual` profile uses documented source priority.
The `bert` profile uses a pinned Japanese BERT encoder and a trained role classifier.
The opt-in `jev` profile uses a hosted, evidence-constrained decision model. Set
`TYPESAFE_API_KEY` in the environment. See [Jev setup and offline replay](jev_research.md).
It keeps raw OCR and cited candidates, selects supported roles, and abstains on
uncertain or unsupported choices. It distinguishes school and tradition categories.
Competing readings/English senses remain alternatives even when the role is selected.
No profile establishes a particular person's identity automatically.

Install BERT with `sh setup.sh --install-ocr --install-bert`, then use
`scan --semantic-profile bert`. The extra installs PyTorch, Transformers and Fugashi.
The approximately 360 MB encoder downloads to the external data directory. Inference
uses local files only. For an existing environment, install the `bert` package extra
and run `python -B -m kanji_translator.install_bert`. Its installer verifies every
encoder file against the packaged, commit-pinned manifest.

`semantic_config.bert_path` or `KOSHIRAI_BERT_DIR` selects another verified local
encoder directory. `semantic_config.bert_device` defaults to `cpu`; `cuda` uses a
compatible GPU. The shipped trained head remains hash checked. Arbitrary custom
head paths are not accepted. Missing BERT dependencies fail explicitly when requested.

Each BERT candidate includes `disambiguation`: the predicted role, full model
probability distribution, margin, selection/review state, reason, head hash and
encoder revision. These probabilities are uncalibrated model outputs. They are not
measured correctness probabilities. `sense_state` identifies competing source
mappings separately from role selection. Literal quantity/unit expressions keep
their deterministic measurement interpretation. Whole source-mapped personal names
own their nested school and given-name fragments. Derivative school/tradition
suffix groups retain the source stem without inventing a full-expression reading.

See [BERT evidence](bert_evaluation.md) for training, comparisons and remaining
failures, and [Jev research](jev_research.md) for the implemented hosted decision option.
Legacy enhancement, generative translation, vision and Tesseract options are
retired and fail with migration guidance. Source-reviewed character corrections
remain separate evidence through `record-review` and corpus review.

Repeated corpus imports verify original source hashes and retain immutable
observations. Changed model proposals create new observations; prior human
reviews survive. `corpus-review` requires explicit completed source-and-mapping
review attestation and a reviewer ID. Nothing is shared automatically. See
[reviewed contributions](reviewed_contributions.md).

To import a completed scan, keep `KANJI_DATA_DIR` set to the same data directory
used for scanning and use the executable path printed by setup (`$cli` in the
README example). Save this request as an external `import.json`, replacing both
paths with your actual input and output locations:

```json
{
  "source_dir": "/path/to/scans",
  "results": "/path/to/output/results.jsonl"
}
```

```sh
"$cli" corpus-ingest --request /path/to/import.json
"$cli" corpus-ingest --request /path/to/import.json
printf '{}\n' | "$cli" corpus-inspect
```

The first import reports added observations. Repeating the same request reports
zero added observations and the existing count. Inspection returns the local
corpus summary; an empty JSON object is a valid inspection request.
