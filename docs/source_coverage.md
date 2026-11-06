# Sources and updates

The bootstrap obtains these public upstream snapshots over HTTPS:

| Source | Download | Role |
| --- | --- | --- |
| JMdict | [JMdict_e.gz](https://www.edrdg.org/pub/Nihongo/JMdict_e.gz) | Word spellings, readings, restricted English senses |
| JMnedict | [JMnedict.xml.gz](https://www.edrdg.org/pub/Nihongo/JMnedict.xml.gz) | Name alternatives and name types |
| KANJIDIC2 | [kanjidic2.xml.gz](https://www.edrdg.org/kanjidic/kanjidic2.xml.gz) | Character readings, glosses, attested variant links |

Copyright James William Breen and the Electronic Dictionary Research and Development
Group. Used under [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/),
with the [EDRDG documentation and terms](https://www.edrdg.org/edrdg/licence.html).
Derived SQLite data retain that license. Significant extracted dictionary data
must retain attribution and applicable share-alike terms; the MIT code license
covers original code only. This project does not imply EDRDG endorsement.

`./setup.sh --update` downloads current snapshots. Each successful atomic build
records source URLs, SHA-256 values, transformations, license and builder version
in `dictionary_releases`; external `release.json` records the retrieval time.
Keep the original gzip files, `NOTICE.txt` and release record with any redistributed
lookup database. Retain the EDRDG documentation and license links. Downstream
interfaces displaying substantial dictionary data must display appropriate attribution.
To reproduce a snapshot, provide those three unchanged gzip files with
`--source-dir`, then check the recorded hashes. Hashes identify retrieved data;
upstream does not supply an independent signature through this installer.
The installer reuses snapshots unless `--update` is explicitly requested.

MeCab and UniDic Lite arrive from PyPI under their own upstream licenses. UniDic Lite
is the modern morphology default; it is not evidence of historical pronunciation.
Historical NINJAL profiles require separately acquired dictionaries and their own
terms, which may include noncommercial/share-alike restrictions. None are bundled.
Optional OCR/image packages and system Tesseract retain their respective licenses;
[PyMuPDF/MuPDF has AGPL-3.0 or commercial licensing](https://pymupdf.readthedocs.io/en/latest/about.html#license-and-copyright),
which users must assess for their distribution. Exact component terms and
installed-distribution qualifications are listed in [data notices](notices/third_party_data.md).

Python Unicode normalization uses the interpreter's Unicode database. See the
[Unicode license](https://www.unicode.org/license.txt) and [included notice](notices/unicode.txt).
No new Unicode IVD or Unihan download is required at setup. The bundled derived
lookup includes registered glyph sequences and selected Japanese Unicode facts;
unregistered variation selectors remain literal and unknown.
KANJIDIC2 links are retrieval alternatives, never destructive spelling replacement.

## Derived sword library

The package resource `resources/sword_library.json.gz` contains bounded factual mappings
from the retained parsed cohort. Every one of 401,990 witness rows receives an
export or rejection disposition in the manifest: 401,979 usable occurrences,
10 unknown-glyph rejections and one unusable form. There are 17,914 distinct
source smith candidates, 33,538 grouped source-form mappings, 3340 terms,
3,627 spellings, 402 concepts, 721 aliases and 125 concept links. Unknown forms
are rejected from factual lookup rather than silently completed.

All three retained smith-register cohorts are included: Club, Nihonto Watch and
the primary private reference. All retained dealer, the primary private reference, the supporting private reference PDF and saved-book witness kinds
are accounted for. Grouped form records retain occurrence counts and source kinds;
untyped forms do not acquire an invented meaning, category or smith identity.
Extracted romanization remains unverified. The export requires Japanese romanization-shaped
tokens and omits English descriptive concept labels and aliases. This conservative
filter can omit valid spellings; omissions do not delete private evidence or prove
that retained readings are correct. The manifest records 362 omitted aliases and
224 omitted descriptive labels; all 402 concept identifiers remain. The manifest counts retained, absent
and rejected prose/non-romanization fields. Distinct same-name smith records have
separate deterministic candidate IDs; these IDs are local release identifiers.

Unicode facts include 2,173 Japanese variant relations, 9,416 registered glyph
sequences, 15,453 Japanese readings/stroke/radical properties and 4,631 MJ
character mappings. Only attested sword-form characters and their explicit variant closure are included.
Other Unicode properties and unrelated characters are excluded with counts because
they are outside Japanese reading and structural lookup; Unicode definitions are
not bundled. MJ readings are retained only when separable kana tokens. Character
and glyph relations never establish identity between people.

Bootstrap imports the hash-verified bundle into the external application database.
Installed wheels use the same records. The combined private master is neither
required at runtime nor distributed. No definitions, captions, page text, source
logs, raw images, private paths or private source identifiers are exported.
MIT permissions cover only original contributions whose rights contributors hold;
third-party source and Unicode terms remain separate.

Maintainers reproduce the bundle using the single parameterized builder:

```sh
"$KANJI_DATA_DIR/environment/bin/python" -m kanji_translator.build_sword_library \
  --master /path/to/private-master.sqlite3 \
  --output /path/to/release/kanji_translator/resources
```

The builder opens the master read-only, selects allowlisted facts, sorts records,
writes deterministic gzip bytes and replaces the bundle and hash manifest using
atomic file replacement (manifest last). Raw context and evidence columns are
never exported. Keep the master and build receipts outside the public checkout.
Identical input and builder versions produce identical resource hashes.
Coverage is of retained parsed records, not all worldwide terminology or verified
semantic correctness; ambiguous extracts remain review candidates.

The public contribution is the postprocessed lookup mapping: normalized kanji,
readings or romanization, candidate smith links, source labels and retained review
status. A combined mapping can record that multiple sources support a form without
redistributing their original entries. Shared labels alone do not prove independent
chains or agreement on a person's identity. The present bundle is a candidate
lookup layer, not a verified consensus identity table: ambiguity is preserved and
no candidate is automatically accepted.

Terms and names remain candidates with source review states. Concept links retain
match basis and uncertainty. No new semantic approval, identity acceptance, or
independent evidence chain is inferred by packaging the library.

## Private input and access

The combined scholarly, dealer, Unicode and historical-name master/training corpus
and ordinary full OCR outputs remain private. Parser code and derived lookup facts
ship here, alongside the explicitly rights-verified public benchmark described
below. A private folder or a “no training” label does not
grant copyright permission. In [Bartz v. Anthropic, June 23, 2025](https://www.govinfo.gov/content/pkg/USCOURTS-cand-3_24-cv-05417/pdf/USCOURTS-cand-3_24-cv-05417-0.pdf),
the court's training fair-use ruling did not excuse acquiring and retaining a
pirated general-purpose library. Named private access is appropriate only where
rights permit; collaborators can instead supply their own licensed originals.
This project does not share or upload private files.

## Public NDL benchmark

The [benchmark](../benchmarks/README.md) samples 50 full scan frames from four
Fujishiro editions, with ten nested raw JPEGs included in this repository. The
remaining forty are fetched and verified by the manifest. These are editions,
not four consecutively numbered volumes. Their public NDL identifiers are
1150503, 1116191, 1116200 and 1125196.

[NDL's reuse guidance](https://www.ndl.go.jp/en/use/reproduction) distinguishes
public-domain material from material merely accessible online by permission.
The [rights receipt](../benchmarks/scan_rights.json) records NDL's public-domain
designation for these exact editions and the absence of frame-specific permission
overrides. Credit: 国立国会図書館 National Diet Library, JAPAN. This finding does
not clear later editions, new translations, or the separate private source corpus.

The benchmark reference is provisional AI pixel review with source-cited reading
and lexical-gloss alternatives. It is not a trusted full transcription or a human
expert translation. Derived EDRDG reference data retain CC BY-SA 4.0 attribution;
the reference protocol and denominators travel with every score.

The current manifest also reconciles kanji, romaji and English fields separately
for every retained witness cohort and every domain-entry source (`mapping_fields`).
Across 401,990 witnesses and 3,265 domain entries it exports 942 occurrences of
bounded English lexical facts. Full definitions, surrounding prose and unsupported
field values remain in the private master; their dispositions are explicit.
The bundle groups forms by English gloss as well as literal/reading, preserving
33,538 distinct source-form mappings. These are retained extraction candidates;
occurrence accounting does not independently verify translations or readings.
The benchmark records its original bundle hashes. This later glossary-field
repair adds no new measured OCR or translation accuracy claim.

The current release adds 67 source-linked glossary mappings. Short English labels summarize the cited the primary private reference definitions; the supporting private reference supplies attested Japanese spellings. Citations retain both chains.
