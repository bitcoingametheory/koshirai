# Data rights

JMdict, JMnedict and KANJIDIC2 are copyright James William Breen and the Electronic
Dictionary Research and Development Group, used under CC BY-SA 4.0.

- [EDRDG license and documentation](https://www.edrdg.org/edrdg/licence.html)
- [CC BY-SA 4.0 license](https://creativecommons.org/licenses/by-sa/4.0/)
- [Source files and transformations](../source_coverage.md)

The generated database contains transformed dictionary data and derived aliases.
Its data rights are separate from the project's MIT code license. Upstream data
are downloaded to external user directories and are excluded from this repository.
No historical NINJAL dictionary is bundled or relicensed. Dependencies keep their
own notices and licenses in the external installation.

## Bundled derived sword facts

The package includes normalized concepts, aliases, terms, historical names and
review states from the current derived library. Attribution is retained in its
public bibliography. All concept and source definition prose, scholarly/dealer captions and raw records
are excluded. MIT grants permissions in original project-owned code and original contributions
to the derived lookup library only to the extent contributors hold those rights. No claim
of ownership or relicensing of third-party source material is made. Public
distribution of selected derived facts and curated contributions does not establish
that extracted or combined data are necessarily free of third-party rights.
No redistribution grant for omitted source works is claimed. Source attribution is not evidence of independent
corroboration or an accepted identity.


The public contribution is the postprocessed lookup mapping: normalized kanji,
readings or romanization, candidate smith links, source labels and retained review
status. A combined mapping can record that multiple sources support a form without
redistributing their original entries. Shared labels alone do not prove independent
chains or agreement on a person's identity. The present bundle is a candidate
lookup layer, not a verified consensus identity table: ambiguity is preserved and
no candidate is automatically accepted.

## Installed and linked dependencies

Dependencies are downloaded or linked into an external installation; the project
MIT license does not replace their terms. Preserve the notices shipped with the
specific versions and their bundled components. This is not a blanket conclusion
that every distribution or deployment satisfies those terms.

| Component | License or applicable terms |
| --- | --- |
| JMdict, JMnedict, KANJIDIC2 and derived dictionary data | [CC BY-SA 4.0, EDRDG](https://www.edrdg.org/edrdg/licence.html) |
| mecab-python3 | BSD wrapper; bundled MeCab has its own BSD/GPL/LGPL alternatives |
| UniDic Lite Python code | MIT or WTFPL; [UniDic 2.1.2 dictionary: BSD](https://github.com/polm/unidic-lite#license), with upstream notices retained |
| Beautiful Soup; pytest test dependency | MIT |
| Pillow | MIT-CMU; bundled libraries retain their notices |
| NumPy | BSD-3-Clause core; installed distribution also declares 0BSD, MIT, Zlib and CC0-1.0 components |
| opencv-python-headless | Apache-2.0 package; bundled components retain their notices |
| PyMuPDF and MuPDF | [AGPL-3.0 or Artifex commercial license](https://pymupdf.readthedocs.io/en/latest/about.html#license-and-copyright) |
| External [NDLOCR-Lite](https://github.com/ndl-lab/ndlocr-lite) | NDL CC BY 4.0; retain upstream notices and dependency/model terms, including the DINOv3 terms identified upstream. Installed separately; no OCR weights are bundled here. |
| External Tesseract and official tessdata | Apache-2.0; retain package/model notices and check any replacement models separately |
| Python Unicode database and selected Unihan/IVD facts | [Unicode License v3 and notice](unicode.txt); only attested character closure is bundled |
| Selected MJ character mappings | [MJ character information table](https://moji.or.jp/mojikiban/mjlist/), Character Information Technology Promotion Council; [CC BY-SA 2.1 Japan](https://creativecommons.org/licenses/by-sa/2.1/jp/). Transformed to selected UCS links and bounded kana readings; these derived records retain that license |

Private the primary private reference/the supporting private reference books, dealer pages, source images, raw definitions and the
combined master/training corpus are excluded. Their applicable source rights are
not replaced by MIT or by bibliography attribution. Named private access requires
appropriate rights; collaborators may supply their own licensed originals.

## Publication is separate from local parsing

Local `text.txt`, `results.jsonl`, and review outputs can reproduce source expression
and private paths. They are not automatically suitable for a public pull request.
Publish only the reviewed, minimal lookup contribution described in
[contributing](../reviewed_contributions.md), with its source and applicable rights stated.
Keeping originals private does not by itself establish fair use for acquisition,
storage, parsing, training, or distribution. The
[Bartz v. Anthropic fair-use order](https://www.govinfo.gov/content/pkg/USCOURTS-cand-3_24-cv-05417/pdf/USCOURTS-cand-3_24-cv-05417-0.pdf)
distinguished training from maintaining a pirated library. It does not give this
project or its outputs blanket legal clearance. Automated publication checks
inspect known patterns and fields; they cannot establish all third-party rights.

## Public-domain benchmark exception

The ten JPEGs in `benchmarks/sample_scans/` and the 50-frame benchmark outputs concern
only the exact NDL editions recorded in [rights.json](../../benchmarks/scan_rights.json).
NDL designates those editions public domain; frame-level permissions were checked
before publication. Follow [NDL's reuse guidance](https://www.ndl.go.jp/en/use/reproduction)
and retain the credit 国立国会図書館 National Diet Library, JAPAN. Public online
access alone is not the criterion used here.

The benchmark annotation is distributed under CC BY-SA 4.0, with EDRDG
JMdict/JMnedict/KANJIDIC2 attribution and entry identifiers for derived readings
and glosses. Its AI review status and uncertainty must remain attached. Model
predictions are proposals, not accepted translations. No model weights or
protected/private source pages are included in this exception.


## Japanese BERT and the role classifier

The optional encoder is Tohoku NLP's `bert-base-japanese-char-v3`, pinned to commit
`ccddee593a9e03a589ae1feedcd4d1eb06d6ba02`. It downloads separately and is distributed
under Apache License 2.0. Its [model card](https://huggingface.co/tohoku-nlp/bert-base-japanese-char-v3)
describes the CC-100/Wikipedia pretraining and character tokenization. Koshirai's
manifest records the exact downloaded file hashes.

The packaged role head is trained on provisional AI annotations with public-domain
Fujishiro OCR context and separately marked synthetic teaching examples. Benchmark
annotations retain their CC BY-SA 4.0 terms and EDRDG attribution described above.
The training examples, split provenance and parameter checksum are published with
the BERT evaluation. No private the primary private reference or the supporting private reference prose enters this classifier's
training examples. Short cited school/tradition facts remain retrieval evidence,
separate from neural training. Model judgments do not certify source truth.
