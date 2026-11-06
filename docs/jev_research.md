# Jev integration and evidence

Jev is TypeSafe's hosted decision model. Koshirai implements the official
[Choice contract](https://docs.typesafe.ai/primitives/choice) and
[System One API](https://docs.typesafe.ai/api/system-one) using Python's standard library.
No vendor skill, router, SDK or background service is installed.

Select `--semantic-profile jev` and set `TYPESAFE_API_KEY` in the process environment.
Do not put the credential in request JSON, the repository, or benchmark files.
The existing local credential was used for authenticated model discovery and live tests.
The default profile remains `contextual`; no hosted call starts under that profile.

## Decisions and constraints

Each complete candidate span gets three independent questions in one request:

1. Which supported semantic role fits: smith, school, tradition, place, or another available role?
2. Which existing cited library candidate fits the meaning and reading?
3. Does this context contain sufficient evidence for a supplied interpretation?

The adapter sends at most 72 characters on each side, the target, and short candidate
facts with pseudonymous citations. It sends no private reference book passages or scans.
The source text is data, not instructions. Responses must match the declared question
and option identifiers. Code validates finite distributions, sums, chosen maxima and
the separate support judgment. Unsupported identifiers cannot create new meanings.
A role selection does not establish a specific person's identity.

Selection requires role probability at least 0.75, a top-to-next margin at least 0.20,
and support score at least 0.75. Candidate-sense selection has its own probability and
margin checks. A role can be selected while competing readings remain unresolved.
Printed measurements retain deterministic quantity/unit interpretation.
Unconfirmed image-text boundaries remain candidates rather than primary selections.

The provider's [confidence documentation](https://docs.typesafe.ai/confidence) distinguishes
confidence from top-option probability. Koshirai does not claim these outputs are
calibrated correctness probabilities on historical Japanese.

## Model, caching and failures

The account exposes `jev-latest` and `jev-preview` aliases. Evaluation uses
`jev-latest` with registry release `2026-10-22T02:00:00+00:00`. This is not an
immutable downloadable checkpoint. The adapter queries authenticated model metadata,
records the release identity and rejects a configured revision mismatch. Live
results may change across provider releases. Frozen responses support exact replay.

Caches bind context, candidate evidence, instructions, adapter version and model
release. They contain decisions, checksums and usage, never credentials. Connection,
rate-limit and selected server failures have three bounded attempts. Authentication,
schema and validation failures remain explicit. There is no silent source-only fallback
when an explicitly requested hosted call fails.

Import the published response cache for offline replay:

```sh
python3 -B -m kanji_translator.jev_context \
  --import-cache benchmarks/jev_decisions.jsonl.gz --target /external/jev-cache
```

Use an external configuration:

```json
{
  "semantic_config": {
    "profile": "jev",
    "jev_cache_dir": "/external/jev-cache",
    "jev_model": "jev-latest",
    "jev_revision": "2026-10-22T02:00:00+00:00",
    "jev_replay_only": true
  }
}
```

Missing cache entries fail explicitly. Offline mode makes no network calls and needs
no key. For live mode, omit `jev_replay_only`; keep the model revision if reproducing
this provider release. `jev_key_env` can select another credential variable name.

## Measured outcome

On 178 recovered source targets, Jev selects 106: 100 match provisional role labels,
6 disagree, and 72 abstain. Selection precision is 94.3%, covering 59.6% of targets.
BERT selects 131 with 130 matches and 1 disagreement. Source priority selects 58
with 43 matches and 15 disagreements. Different coverage prevents treating those
precision values as complete-system accuracy. The targets and labels are already
exposed development/regression evidence, not expert truth or a fresh blind test.

All 50 original Fujishiro scans complete under Jev. Complete sword groups have
30 matches, 4 benchmark rejections and 295 misses: 88.2% precision and 9.2% recall.
Jev is more conservative and misses more terms than BERT or source priority.
It abstains on some terse headings, including the tested ambiguous unspaced heading.
The hosted option is useful to compare and review; it does not establish universal
semantic or English-translation superiority. The local BERT option performs better
on recovered-target selection in this experiment.

See [the complete Jev report](../benchmarks/jev_evaluation.json),
[all approaches tried](approaches.md), and the [researcher guide](researcher_guide.md).
