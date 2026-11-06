# File guide

The package has one implementation. Standard Python and packaging names are retained where tools require them. Data IDs stay immutable while scan filenames describe the edition.

Runtime files support scanning and lookup; the other categories support installation, reproducibility, review and licensing. Historical benchmark receipts remain evidence, not a second implementation.

| File | Role | Why retained |
| --- | --- | --- |
| [.gitignore](../.gitignore) | installation and entry points | Keeps private inputs, caches and environments out of releases. |
| [LICENSE](../LICENSE) | installation and entry points | Permissions for original project contributions. |
| [README.md](../README.md) | installation and entry points | Researcher starting point and accurate capability statement. |
| [benchmarks/README.md](../benchmarks/README.md) | evaluation evidence | Canonical counting, annotation, supervision and evaluation interpretation rules. |
| [benchmarks/bert_evaluation.json](../benchmarks/bert_evaluation.json) | evaluation evidence | BERT training, same-source comparison, installed inference and reproduction receipts. |
| [benchmarks/bert_predictions.jsonl.gz](../benchmarks/bert_predictions.jsonl.gz) | evaluation evidence | Frozen BERT page predictions with pseudonymous provenance and local paths removed. |
| [benchmarks/bert_source_priority_predictions.jsonl.gz](../benchmarks/bert_source_priority_predictions.jsonl.gz) | evaluation evidence | Paired source-priority page predictions for the BERT comparison. |
| [benchmarks/bert_training.json.gz](../benchmarks/bert_training.json.gz) | evaluation evidence | Frozen public OCR labels and synthetic teaching cases used for classifier reproduction. |
| [benchmarks/boundary_evaluation.json](../benchmarks/boundary_evaluation.json) | evaluation evidence | Paired complete-group counts, failed first pass and bounded retained-OCR evidence. |
| [benchmarks/boundary_predictions.jsonl.gz](../benchmarks/boundary_predictions.jsonl.gz) | evaluation evidence | Frozen same-OCR predictions for the Japanese technical-boundary repair. |
| [benchmarks/build_role_facts.py](../benchmarks/build_role_facts.py) | evaluation | Derive bounded school/tradition facts from hash-selected PrimaryReference headings. |
| [benchmarks/compare_predictions.py](../benchmarks/compare_predictions.py) | evaluation | Compare complete sword groups only after verifying identical pages and OCR. |
| [benchmarks/download_scans.py](../benchmarks/download_scans.py) | evaluation | Fetch hash-bound public full pages outside this checkout. |
| [benchmarks/evaluate_bert.py](../benchmarks/evaluate_bert.py) | evaluation | Compare source priority and BERT on the same frozen, recovered source targets. |
| [benchmarks/evaluate_frontier.py](../benchmarks/evaluate_frontier.py) | evaluation | Prepare, run and compare the same bounded Japanese corpus on Astra and Sol. |
| [benchmarks/evaluate_jev.py](../benchmarks/evaluate_jev.py) | evaluation | Compare live or replayed Jev with source priority on frozen recovered targets. |
| [benchmarks/evaluate_layout.py](../benchmarks/evaluate_layout.py) | evaluation | Score frozen source-image panel/link targets without supplying labels to inference. |
| [benchmarks/evaluate_semantics.py](../benchmarks/evaluate_semantics.py) | evaluation | Frozen same-OCR 10/50-page execution and exhaustive grouped-mention scoring. |
| [benchmarks/export_predictions.py](../benchmarks/export_predictions.py) | evaluation | Publish frozen prediction evidence without machine-local crop cache paths. |
| [benchmarks/historical_evidence.json](../benchmarks/historical_evidence.json) | evaluation evidence | Sole consolidated original/corrected annotations and compact negative results preserved independently of Git history. |
| [benchmarks/jev_decisions.jsonl.gz](../benchmarks/jev_decisions.jsonl.gz) | evaluation evidence | Checksum-verified provider decisions for credential-free offline replay. |
| [benchmarks/jev_evaluation.json](../benchmarks/jev_evaluation.json) | evaluation evidence | Live Jev, conditional-role, page, layout and offline-replay evidence. |
| [benchmarks/jev_predictions.jsonl.gz](../benchmarks/jev_predictions.jsonl.gz) | evaluation evidence | Frozen Jev page predictions without local cache paths. |
| [benchmarks/native_semantics_evaluation.json](../benchmarks/native_semantics_evaluation.json) | evaluation evidence | Native entry/clause evidence, paired location policies, failed passes and pending model comparison. |
| [benchmarks/native_semantics_predictions.jsonl.gz](../benchmarks/native_semantics_predictions.jsonl.gz) | evaluation evidence | Frozen same-OCR native-entry predictions without machine-local cache paths. |
| [benchmarks/sample_manifest.json](../benchmarks/sample_manifest.json) | evaluation evidence | Public sample frame identities, hashes and reuse rights used by downloader/release checks. |
| [benchmarks/sample_scans/fujishiro_koto_1116200_0011.jpg](../benchmarks/sample_scans/fujishiro_koto_1116200_0011.jpg) | evaluation evidence | Public original scan fujishiro_koto_1116200_0011 for repository-only workflow validation; hash/rights in sample manifest. |
| [benchmarks/sample_scans/fujishiro_koto_1116200_0077.jpg](../benchmarks/sample_scans/fujishiro_koto_1116200_0077.jpg) | evaluation evidence | Public original scan fujishiro_koto_1116200_0077 for repository-only workflow validation; hash/rights in sample manifest. |
| [benchmarks/sample_scans/fujishiro_koto_1116200_0099.jpg](../benchmarks/sample_scans/fujishiro_koto_1116200_0099.jpg) | evaluation evidence | Public original scan fujishiro_koto_1116200_0099 for repository-only workflow validation; hash/rights in sample manifest. |
| [benchmarks/sample_scans/fujishiro_koto_1116200_0239.jpg](../benchmarks/sample_scans/fujishiro_koto_1116200_0239.jpg) | evaluation evidence | Public original scan fujishiro_koto_1116200_0239 for repository-only workflow validation; hash/rights in sample manifest. |
| [benchmarks/sample_scans/fujishiro_shinto_1116191_0144.jpg](../benchmarks/sample_scans/fujishiro_shinto_1116191_0144.jpg) | evaluation evidence | Public original scan fujishiro_shinto_1116191_0144 for repository-only workflow validation; hash/rights in sample manifest. |
| [benchmarks/sample_scans/index.json](../benchmarks/sample_scans/index.json) | evaluation evidence | Maps immutable public frame IDs to researcher-readable image filenames. |
| [benchmarks/sample_scans/shinto_hamon_signatures_1125196_0051.jpg](../benchmarks/sample_scans/shinto_hamon_signatures_1125196_0051.jpg) | evaluation evidence | Public original scan shinto_hamon_signatures_1125196_0051 for repository-only workflow validation; hash/rights in sample manifest. |
| [benchmarks/sample_scans/shinto_hamon_signatures_1125196_0055.jpg](../benchmarks/sample_scans/shinto_hamon_signatures_1125196_0055.jpg) | evaluation evidence | Public original scan shinto_hamon_signatures_1125196_0055 for repository-only workflow validation; hash/rights in sample manifest. |
| [benchmarks/sample_scans/shinto_hamon_signatures_1125196_0093.jpg](../benchmarks/sample_scans/shinto_hamon_signatures_1125196_0093.jpg) | evaluation evidence | Public original scan shinto_hamon_signatures_1125196_0093 for repository-only workflow validation; hash/rights in sample manifest. |
| [benchmarks/sample_scans/shinto_hamon_signatures_1125196_0095.jpg](../benchmarks/sample_scans/shinto_hamon_signatures_1125196_0095.jpg) | evaluation evidence | Public original scan shinto_hamon_signatures_1125196_0095 for repository-only workflow validation; hash/rights in sample manifest. |
| [benchmarks/sample_scans/shinto_hamon_signatures_1125196_0118.jpg](../benchmarks/sample_scans/shinto_hamon_signatures_1125196_0118.jpg) | evaluation evidence | Public original scan shinto_hamon_signatures_1125196_0118 for repository-only workflow validation; hash/rights in sample manifest. |
| [benchmarks/scan_rights.json](../benchmarks/scan_rights.json) | evaluation evidence | Original public-scan rights receipts supporting redistributable examples. |
| [benchmarks/semantic_evaluation.json](../benchmarks/semantic_evaluation.json) | evaluation evidence | Current measured workflow/evaluation receipt with unscored limitations. |
| [benchmarks/semantic_predictions.jsonl.gz](../benchmarks/semantic_predictions.jsonl.gz) | evaluation evidence | Same-scan general, exact and contextual predictions needed to reproduce published grouping scores. |
| [benchmarks/semantic_references.json](../benchmarks/semantic_references.json) | evaluation evidence | Frozen source-only declared-region annotations, public frame identities and reuse citations. |
| [benchmarks/train_bert.py](../benchmarks/train_bert.py) | evaluation | Train a reproducible BERT role head with page-disjoint source and template tests. |
| [docs/approaches.md](../docs/approaches.md) | researcher documentation | Documents installation, evidence interpretation, contribution, source coverage, licenses or this audit. |
| [docs/bert_evaluation.md](../docs/bert_evaluation.md) | researcher documentation | Documents installation, evidence interpretation, contribution, source coverage, licenses or this audit. |
| [docs/evaluation.html](../docs/evaluation.html) | researcher documentation | Documents installation, evidence interpretation, contribution, source coverage, licenses or this audit. |
| [docs/file_guide.md](../docs/file_guide.md) | researcher documentation | Documents installation, evidence interpretation, contribution, source coverage, licenses or this audit. |
| [docs/file_inventory.json](../docs/file_inventory.json) | researcher documentation | Documents installation, evidence interpretation, contribution, source coverage, licenses or this audit. |
| [docs/jev_research.md](../docs/jev_research.md) | researcher documentation | Documents installation, evidence interpretation, contribution, source coverage, licenses or this audit. |
| [docs/library_coverage.json](../docs/library_coverage.json) | researcher documentation | Documents installation, evidence interpretation, contribution, source coverage, licenses or this audit. |
| [docs/native_semantics.md](../docs/native_semantics.md) | researcher documentation | Documents installation, evidence interpretation, contribution, source coverage, licenses or this audit. |
| [docs/notices/third_party_data.md](../docs/notices/third_party_data.md) | researcher documentation | Documents installation, evidence interpretation, contribution, source coverage, licenses or this audit. |
| [docs/notices/unicode.txt](../docs/notices/unicode.txt) | researcher documentation | Documents installation, evidence interpretation, contribution, source coverage, licenses or this audit. |
| [docs/researcher_guide.md](../docs/researcher_guide.md) | researcher documentation | Documents installation, evidence interpretation, contribution, source coverage, licenses or this audit. |
| [docs/reviewed_contributions.md](../docs/reviewed_contributions.md) | researcher documentation | Documents installation, evidence interpretation, contribution, source coverage, licenses or this audit. |
| [docs/source_coverage.md](../docs/source_coverage.md) | researcher documentation | Documents installation, evidence interpretation, contribution, source coverage, licenses or this audit. |
| [kanji_translator/__init__.py](../kanji_translator/__init__.py) | application | Canonical public parser API. All operations preserve source-owned originals. |
| [kanji_translator/__main__.py](../kanji_translator/__main__.py) | application | Package integration and public imports. |
| [kanji_translator/audit_library.py](../kanji_translator/audit_library.py) | library maintenance | Count retained mappings and inspect every stored English pair reproducibly. |
| [kanji_translator/bert_context.py](../kanji_translator/bert_context.py) | application | Frozen Japanese BERT features and a trained, evidence-constrained role head. |
| [kanji_translator/build_sword_library.py](../kanji_translator/build_sword_library.py) | library maintenance | Build a factual release from an explicitly supplied read-only parsed master. |
| [kanji_translator/candidate_lookup.py](../kanji_translator/candidate_lookup.py) | application | Compatibility API for exact lexical lookup; gap completion is retired. |
| [kanji_translator/command_line.py](../kanji_translator/command_line.py) | application | The sole public executable parser entry point; JSON in, deterministic JSON out. |
| [kanji_translator/context_constraints.py](../kanji_translator/context_constraints.py) | application | Typed constraints; absent context provides no evidence. |
| [kanji_translator/data_paths.py](../kanji_translator/data_paths.py) | application | External writable locations; no data or environments belong in the checkout. |
| [kanji_translator/dictionary_lookup.py](../kanji_translator/dictionary_lookup.py) | application | One typed lexical adapter for native text and recognized literal spans. |
| [kanji_translator/dictionary_sources.py](../kanji_translator/dictionary_sources.py) | application | Streaming public dictionary builder. Source restrictions remain first-class data. |
| [kanji_translator/document_layout.py](../kanji_translator/document_layout.py) | application | Source-owned document groups and associations, before lexical enrichment. |
| [kanji_translator/document_parser.py](../kanji_translator/document_parser.py) | application | Native -> exact reviewed transcript -> failed-region OCR -> proposal queue. |
| [kanji_translator/entry_structure.py](../kanji_translator/entry_structure.py) | application | Read explicit Japanese dictionary-entry fields without inventing name splits. |
| [kanji_translator/frontier_semantics.py](../kanji_translator/frontier_semantics.py) | application | Opt-in, bounded native-Japanese model experiment with closed source choices. |
| [kanji_translator/glossary_bridge.py](../kanji_translator/glossary_bridge.py) | application | Join reviewed PrimaryReference glossary headwords to attested SupportingReference kanji forms. |
| [kanji_translator/image_regions.py](../kanji_translator/image_regions.py) | application | Bounded native-pixel layout/crops; derived data only, no source-owner writes. |
| [kanji_translator/install_bert.py](../kanji_translator/install_bert.py) | installation | Install the pinned Japanese BERT encoder into an external directory. |
| [kanji_translator/install_dictionaries.py](../kanji_translator/install_dictionaries.py) | installation | Credential-free HTTPS downloads and repeatable external public-data build. |
| [kanji_translator/install_ocr.py](../kanji_translator/install_ocr.py) | installation | Install the pinned CPU NDLOCR reader outside the checkout, without OS changes. |
| [kanji_translator/japanese_clauses.py](../kanji_translator/japanese_clauses.py) | application | Bounded Japanese relation proposals and evidence-linked English presentation. |
| [kanji_translator/jev_context.py](../kanji_translator/jev_context.py) | application | Opt-in Jev decisions over cited candidates, with strict validation and local replay. |
| [kanji_translator/meaning_selection.py](../kanji_translator/meaning_selection.py) | application | Separate source English fragments, lexical candidates and selected meanings. |
| [kanji_translator/readers/__init__.py](../kanji_translator/readers/__init__.py) | application | Native HTML and local OCR readers. |
| [kanji_translator/readers/html/__init__.py](../kanji_translator/readers/html/__init__.py) | application | Internal canonical parser components. |
| [kanji_translator/readers/html/nihonto_club.py](../kanji_translator/readers/html/nihonto_club.py) | application | Pure saved-DOM Club parsing; acquisition remains with scrapers. |
| [kanji_translator/readers/ocr/__init__.py](../kanji_translator/readers/ocr/__init__.py) | application | The maintained literal Japanese OCR engine. |
| [kanji_translator/readers/ocr/ndlocr_lite.py](../kanji_translator/readers/ocr/ndlocr_lite.py) | application | NDLOCR-Lite page recognition; literal text and regions remain proposals. |
| [kanji_translator/readers/ocr/retained.py](../kanji_translator/readers/ocr/retained.py) | application | Read a hash-bound library OCR snapshot without OCR calls or line joining. |
| [kanji_translator/reading_candidates.py](../kanji_translator/reading_candidates.py) | application | Optional literal-aligned reading evidence; no inferred historical-name readings. |
| [kanji_translator/region_enrichment.py](../kanji_translator/region_enrichment.py) | application | Cache the single literal lexical stage; semantic interpretation follows it. |
| [kanji_translator/request_contracts.py](../kanji_translator/request_contracts.py) | application | Finite public request validation and deterministic serialization. |
| [kanji_translator/research_corpus.py](../kanji_translator/research_corpus.py) | application | Private, immutable scan observations and explicit human mapping reviews. |
| [kanji_translator/resource_limits.py](../kanji_translator/resource_limits.py) | application | Admission and continuous reserve checks for one owned CUDA process group. |
| [kanji_translator/resources/bert_base_manifest.json](../kanji_translator/resources/bert_base_manifest.json) | runtime data | Pinned Japanese BERT encoder file identities and hashes. |
| [kanji_translator/resources/bert_head.json.gz](../kanji_translator/resources/bert_head.json.gz) | runtime data | Trained contextual role classifier parameters; no source prose. |
| [kanji_translator/resources/bert_head_manifest.json](../kanji_translator/resources/bert_head_manifest.json) | runtime data | Classifier checksum, encoder revision and training provenance. |
| [kanji_translator/resources/data_licenses.txt](../kanji_translator/resources/data_licenses.txt) | runtime data | Required attribution for bundled derived facts. |
| [kanji_translator/resources/semantic_roles.json](../kanji_translator/resources/semantic_roles.json) | runtime data | Cited private-reference school, tradition and complete-name role facts. |
| [kanji_translator/resources/sword_library.json.gz](../kanji_translator/resources/sword_library.json.gz) | runtime data | Source-supported term/name facts used by literal span matching. |
| [kanji_translator/resources/sword_library_manifest.json](../kanji_translator/resources/sword_library_manifest.json) | runtime data | Checks bundled library hashes, counts and source licensing. |
| [kanji_translator/result_cache.py](../kanji_translator/result_cache.py) | application | Content-addressed optional derived cache; every routing dependency is explicit. |
| [kanji_translator/reviewed_readings.py](../kanji_translator/reviewed_readings.py) | application | Explicit human review staging and exact source-bound reuse. |
| [kanji_translator/scan_folder.py](../kanji_translator/scan_folder.py) | application | Local pages -> regions -> OCR -> core Japanese -> sword facts -> review files. |
| [kanji_translator/semantic_groups.py](../kanji_translator/semantic_groups.py) | application | Literal, source-supported span matching and contextual semantic selection. |
| [kanji_translator/semantic_roles.py](../kanji_translator/semantic_roles.py) | application | Single owner of cited school, tradition and complete-name role assertions. |
| [kanji_translator/source_evidence.py](../kanji_translator/source_evidence.py) | application | Read-only reviewed evidence reuse. Explicit human reviews remain separate from model proposals. |
| [kanji_translator/sword_library.py](../kanji_translator/sword_library.py) | application | Portable derived sword facts. Source prose and private records are absent. |
| [kanji_translator/text_normalization.py](../kanji_translator/text_normalization.py) | application | Single text representation and literal-offset owner. |
| [llms.txt](../llms.txt) | installation and entry points | Repository-only instructions for researcher agents. |
| [pyproject.toml](../pyproject.toml) | installation and entry points | Package metadata, pinned dependencies and executable entry points. |
| [setup.sh](../setup.sh) | installation and entry points | One-command external-environment installation. |
| [tests/check_release.py](../tests/check_release.py) | verification | Verifies check release behavior and its current source/evidence contract. |
| [tests/test_bert_context.py](../tests/test_bert_context.py) | verification | Verifies bert context behavior and its current source/evidence contract. |
| [tests/test_bilingual_alignments.py](../tests/test_bilingual_alignments.py) | verification | Verifies bilingual alignments behavior and its current source/evidence contract. |
| [tests/test_dictionary_sources.py](../tests/test_dictionary_sources.py) | verification | Verifies dictionary sources behavior and its current source/evidence contract. |
| [tests/test_document_parser.py](../tests/test_document_parser.py) | verification | Verifies document parser behavior and its current source/evidence contract. |
| [tests/test_frontier_semantics.py](../tests/test_frontier_semantics.py) | verification | Verifies frontier semantics behavior and its current source/evidence contract. |
| [tests/test_image_regions.py](../tests/test_image_regions.py) | verification | Verifies image regions behavior and its current source/evidence contract. |
| [tests/test_install_ocr.py](../tests/test_install_ocr.py) | verification | Verifies install ocr behavior and its current source/evidence contract. |
| [tests/test_jev_context.py](../tests/test_jev_context.py) | verification | Verifies jev context behavior and its current source/evidence contract. |
| [tests/test_meaning_selection.py](../tests/test_meaning_selection.py) | verification | Verifies meaning selection behavior and its current source/evidence contract. |
| [tests/test_native_semantics.py](../tests/test_native_semantics.py) | verification | Verifies native semantics behavior and its current source/evidence contract. |
| [tests/test_ndlocr_lite.py](../tests/test_ndlocr_lite.py) | verification | Verifies ndlocr lite behavior and its current source/evidence contract. |
| [tests/test_research_corpus.py](../tests/test_research_corpus.py) | verification | Verifies research corpus behavior and its current source/evidence contract. |
| [tests/test_resource_limits.py](../tests/test_resource_limits.py) | verification | Verifies resource limits behavior and its current source/evidence contract. |
| [tests/test_retained_ocr.py](../tests/test_retained_ocr.py) | verification | Verifies retained ocr behavior and its current source/evidence contract. |
| [tests/test_reviewed_readings.py](../tests/test_reviewed_readings.py) | verification | Verifies reviewed readings behavior and its current source/evidence contract. |
| [tests/test_scan_folder.py](../tests/test_scan_folder.py) | verification | Verifies scan folder behavior and its current source/evidence contract. |
| [tests/test_semantic_evaluation.py](../tests/test_semantic_evaluation.py) | verification | Verifies semantic evaluation behavior and its current source/evidence contract. |
| [tests/test_semantic_groups.py](../tests/test_semantic_groups.py) | verification | Verifies semantic groups behavior and its current source/evidence contract. |
| [tests/test_source_evidence.py](../tests/test_source_evidence.py) | verification | Verifies source evidence behavior and its current source/evidence contract. |
| [tests/test_sword_library.py](../tests/test_sword_library.py) | verification | Verifies sword library behavior and its current source/evidence contract. |
| [tests/test_text_parsing.py](../tests/test_text_parsing.py) | verification | Verifies text parsing behavior and its current source/evidence contract. |
| [tools/audit_repository.py](../tools/audit_repository.py) | maintenance | Rebuilds the complete file inventory and checks syntax without changing source data. |
