# Contribution and security

Fork or clone from the hosting location chosen by the maintainer. Run
`SETUP_EXTRAS=images,test ./setup.sh` and then the external environment's
`python -m pytest`. Tests use synthetic small records; installed public dictionaries
can be exercised separately with the examples in the README.

Keep implementation in `kanji_translator`, regression tests in `tests` and concise documentation
in `docs`. Avoid adding private collection extracts, reviewer records, credentials,
user paths, databases, unreviewed model weights or generated history. Use external user data
and cache locations. Filename components must be shorter than 50 characters;
the entire checkout and staged content must each remain below 500,000,000 bytes.

For a pull request, run the tests above, `git diff --check`, and inspect
`git diff --cached` before pushing your branch. The maintainer runs
`python3 -B tests/check_release.py` after preparing the replacement root commit: that
release-only guard requires the canonical origin, main branch, matching index
and one root commit, so it is not a contributor-fork command. It checks physical
files, names, size and selected privacy patterns, including staged and committed
content. Review every diff manually and use a dedicated secret scanner where
available. Pattern checks cannot prove absence of every secret or identify all PII.
No code, setup or test should silently run cloud inference or change global packages.

For a suspected security issue, use the hosting service's private reporting channel
if one has been configured. Otherwise contact the maintainer through an established
private channel. Do not post credentials or sensitive source material in a public
issue. The hosting location is https://github.com/bitcoingametheory/koshirai.

## Parsing fixes and updated lookup data

Open a pull request against `main` with the concrete input failure, expected
behavior and the checks you ran. Keep the implementation directly in `kanji_translator/`;
`pyproject.toml` maps that directory to the `kanji_translator` import package.
Install with setup before testing. Add a small synthetic regression reproducer
for a parsing bug. For layouts, describe orientation, file type and affected
regions; include a rights-cleared minimal fixture only when redistribution is
permitted. Retain original Unicode, page geometry and explicit uncertainty.
Never use a model guess as a human-reviewed label.

For benchmark changes, preserve the frozen evaluation sample and its published
receipts. Propose reference corrections separately from parser/model changes,
cite the exact frame and rectangle, explain the old and new readings, and name
the review status. Do not silently rewrite a reference after inspecting a model's
errors. A new sample needs a recorded selection rule before predictions and a
separate version. Keep test pages out of training and tuning data.

An NDL scan fixture needs the exact edition/frame public-domain or redistribution
record, original URL, SHA-256 and NDL attribution. Being visible online is
insufficient. The existing ten-image benchmark exception does not authorize
uploading other books or protected scans. References derived from EDRDG data
retain CC BY-SA 4.0 attribution and the applicable license.

For updated parsing or lookup facts, explain the source, access date, applicable
license/redistribution permission, fields changed and extraction/normalization
rules. Submit only minimal rights-cleared factual mappings with attribution and
review status. Keep ambiguous candidates separate. Raw books, page text,
translations, scans, private source IDs, review exports and full master databases
must stay outside the pull request. Having local access alone does not authorize
redistribution. If rights are unclear, describe the proposed transformation
without uploading source content.

Bundled resources must be regenerated through `kanji_translator.build_sword_library`
using an authorized external master, with manifest counts/hashes and data notices
updated together. Include reproducible build instructions and conservation checks
for unchanged records. A new local NDL book can be tested through `scan` without
adding it to the bundle or changing accepted source cohorts. Report pages
attempted, failed and unresolved separately from any source-reviewed accuracy
measurement. The maintainer reviews the diff and release checks before merging;
public release history is maintained as one root commit.

Fork the repository, create a branch from the current `main`, commit only the
reviewed parser/test/documentation changes, and open the pull request against
`bitcoingametheory/koshirai:main`. Do not force-push the upstream branch. Because
release history is replaced, base each new contribution on the current release.

Contributors do not need the private master. For a data correction, include a
small table in the pull-request description with `literal`, `printed_romaji`
(or null), pseudonymous source ID and page/region locator, proposed review state, rights basis
and the reason for the change. Mark uncertainty explicitly. The maintainer applies
accepted rows to the private build input, regenerates the bundle and manifest,
and verifies the resulting diff. Never attach a full `results.jsonl` export.

For local corpus mappings, run `corpus-ingest`, inspect originals, then explicitly
record `corpus-review`. A `lookup` response includes each local review ID,
observation ID, original OCR, corrected literal, optional reading/English, source
hash and file/page/region locator. Use those identifiers in a proposed correction.
Attach only rights-cleared minimal fixtures and the review decision; keep private
source paths, reviewer contact details, credentials and the corpus database out of
the pull request. A maintainer must review source evidence and ambiguous senses
before integrating an update into the bundled library. Local acceptance does not
automatically publish a mapping or establish a historical smith identity.


## Improved classifier data

A scholarly kanji/English/romanized-reading pair becomes a derived library mapping
after source review. It does not automatically train a classifier. For BERT, add
reviewed role labels and surrounding text to an external training dataset. Preserve
source/work identifiers privately and use pseudonymous identifiers in public data.
Split by source work before training. Keep frozen test data out of tuning. The
`benchmarks/train_bert.py` script accepts an external JSON dataset or the published
compressed teaching/regression data. It writes weights, hashes and evaluation reports
to an external directory. Do not publish private training inputs with the weights.

A model-data pull request should describe changed mappings or labels, the rights
basis, review method, source split, reproduction command, parameter/data hashes,
category-specific errors and before/after coverage. Include a minimal permitted
example. Arrange private evidence review with the maintainer when public evidence
cannot be shared. Required attribution stays intact. The maintainer reviews and
regenerates packaged parameters, manifests and release evidence before publication.
The hosted Jev model is not locally retrained; updated library candidates feed its
next decision request. No inference call is claimed as completed model training.

For a private master that still contains original source identifiers, pass an
external JSON label map through `build_sword_library --source-map /external/source-map.json`.
The builder applies that map while reading records, before source matching and
glossary bridging. It does not alter the private master. Keep the mapping file
private. Preserve required third-party attribution; use the release check to reject
accidentally restored private reference names.
