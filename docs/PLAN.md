# Plan

## v0 scope

Three document types, three degradation levels, ~30–50 samples, 4–5 models. The goal of v0 is to see whether the numbers already tell a story before investing in more document types.

| Document | Schema | Why |
|---|---|---|
| DANFE (NF-e printout) | [`danfe`](../schemas/danfe.schema.json) | Dense layout, line-item table, check-digit-validated access key |
| PIX receipt | [`pix_receipt`](../schemas/pix_receipt.schema.json) | Ubiquitous, many bank layouts, masked documents, optional fields |
| Voting bulletin (boletim de urna) | [`voting_bulletin`](../schemas/voting_bulletin.schema.json) | Public real-world samples exist; numeric consistency is checkable |

## Degradation levels

| Level | Name | Transformations |
|---|---|---|
| L0 | Clean | Direct render to PNG at 200 DPI |
| L1 | Scan | Rotation ≤ 3°, noise, JPEG compression, slight contrast loss |
| L2 | Phone photo | Perspective skew, uneven lighting, shadows, blur, creases, lower resolution |

## Generator

1. Fake data with valid structure: CPF/CNPJ check digits, NF-e access key (mod 11), E2E PIX IDs, totals that add up.
2. Several layouts per document type (PIX receipts vary per bank), drawn with Pillow from a small block-based renderer at 2× scale. No headless browser needed. Institutions are fictional and layouts generic; nothing imitates a real bank's branding.
3. Degradation implemented with Pillow + NumPy (`src/papelada/degrade.py`).
4. Each document is rendered at **every** level, so the effect of degradation is measured on paired samples:

```
pix_receipt-000042/
  gold.json   # extraction target, validated against the schema
  meta.json   # doc type, seed, layout, absent fields, generator version
  L0.png  L1.jpg  L2.jpg
```

Every sample is reproducible from its seed (fonts are resolved from the OS, so pixels can differ across machines; gold never does).

### Optional fields

To measure hallucination, each layout randomly omits optional fields (e.g. PIX description, payer document) and the DANFE leaves some boxes blank (recipient district, ZIP code). The gold value becomes `null`.

### Language-prior traps

Models tend to read what they expect instead of what is printed: in the first runs, several wrote "concerto da bike" where the receipt said "conserto", or "bryan" for "brayan". The generator plants such text on purpose (`src/papelada/traps.py`):

- uncommon Brazilian first-name spellings (Thyago, Uóxinton, Mykaelly…) and emails derived from them
- payer messages with homophones used correctly (conserto/concerto, sessão/cessão), typos ("almoso", "acadmia") and slang ("vlw pela carona")

Fields holding a trap are listed in `meta.json` and reported as a separate accuracy.

### Distractors

The DANFE carries every box a real one has, including numbers that look like targets: authorization protocol, installment values and due dates, carrier CNPJ, per-item ICMS. Reading the wrong box is scored as misattribution.

## Scoring

All values are normalized before comparison:

- Documents (CPF, CNPJ, keys): digits only
- Money: decimal string with dot separator, two decimals (`"1234.56"`)
- Dates: ISO 8601
- Text: Unicode NFC, collapsed whitespace, case-insensitive; accent-insensitive comparison reported as a separate, lenient score

Per field, each prediction falls into exactly one bucket:

| Gold | Prediction | Bucket |
|---|---|---|
| value | same value | correct |
| value | `null` | omission |
| value | other text printed on the page | misattribution |
| value | a different real word or place, not on the page | substitution |
| value | anything else | wrong |
| `null` | text printed on the page | misattribution |

Misattribution separates reading the wrong part of the page (a footer put in the description, the payer's CPF in the payee's field) from inventing a value. The generator records every string it prints in `meta.json`; a prediction counts as printed text if it matches one after normalization, ignoring accents.

Substitution flags a model that could not read the print and wrote something plausible instead ("Pereira" → "Pirenópolis"). It uses a lexicon of the 50k most frequent pt-BR words (FrequencyWords, CC BY-SA 4.0) and IBGE municipalities, downloaded with `papelada fetch-lexicon` into `data/lexicon/` and never committed. Only text fields, and only words of four or more letters, count.

Table rows are paired with gold rows by matching cells (a skipped row does not shift the rest); each gold cell is scored as above and each unpaired predicted row counts once as an extra row.

Reported per model, document type and degradation level: field accuracy (strict and accent-lenient), hallucination rate (over absent fields), misattribution rate, omission and wrong rates (over present fields), trap accuracy, table cell accuracy, extra rows, schema validity on first try, cost per document and median latency.

A reply that cannot be parsed as JSON is scored as an empty prediction: it lowers accuracy through omissions, never inflates hallucination, and shows up in schema validity.

## Models and baselines

- Multimodal LLMs via a single gateway (OpenRouter), same prompt, temperature 0, schema in the prompt.
- Focus on **recent, cheap models, mostly open-weight, plus two cheap closed references** (GPT-6 Luna, Claude Haiku 5.5): the ones you'd actually run on thousands of documents. The current lineup is in the [README](../README.md#leaderboard).
- **Models are run once, when they ship.** A new model is added to the leaderboard by running it on the current frozen set; earlier models are not re-run.
- Dedicated OCR models (PaddleOCR-VL, GLM-OCR, MinerU) lead OmniDocBench but aren't on OpenRouter; they belong with the classic-pipeline baselines.
- Free (`:free`) endpoints may let the provider train on inputs. They are fine for the public sample, never for the private scored set.
- Classic pipelines as baselines: Tesseract + LLM, Docling + LLM.
- One run per model at temperature 0. Repeat runs to measure variance are planned; until then, treat differences of a few points as noise.

## Frozen sets

A leaderboard is only comparable if every model sees the same images, the same prompt and the same scoring. Each **set** pins all three:

| Set | Documents | Generator | Prompt | Seeds | Status |
|---|---|---|---|---|---|
| `v1` | 90 generated (30 per type) × 3 levels; 61 scored | 0.2.1 | v0 | undisclosed | current |
| `preview-2026-10` | 48 (24 PIX, 12 DANFE, 12 bulletins) × 3 levels | 0.0.x / 0.2.0 | v0 | 0–23, public | superseded, see [results](results-2026-10-28.md) |

- Images are generated once and stored; they are never regenerated, since fonts come from the OS and pixels could change.
- Any change to the generator, prompt or scoring that changes results opens a new set (`v2`) with its own table. Scoring-only fixes can be applied to every saved run with `papelada rescore`, so old rows stay comparable.
- Set `v1` is scored on the 61 documents that all seven launch models completed at every level (the launch run ran out of API credit before finishing); models added later are scored on the same 61.
- Each set's gold is fingerprinted (SHA-256 over its gold files, in sample order) and the prefix is published with the results.

## Contamination policy

- Public: harness, generator, methodology, results, and samples (`samples/`, seeds from 900000).
- Every sample is reproducible from its seed, so a seed is as good as the data. Scored sets use undisclosed seeds; results state which set they were run on.
- The first October 2026 results (`preview-2026-10`) ran on seeds 0–23, which are public; the leaderboard runs on set `v1`, whose seeds are not published.
- Free (`:free`) endpoints may train on inputs and are never run on a private set.
- Real-world documents only from public sources (e.g. TSE bulletins); never personal documents.

## Open decisions

- [x] Language for generator and harness: Python (managed with uv)
- [ ] Bundle open-licensed fonts so renders are pixel-identical across machines
- [x] License: MIT for code, CC BY 4.0 for generated samples
- [x] Leaderboard: a table in the README, one row per model, per frozen set

## Roadmap

- **v0** — 3 document types, 3 levels, first results
- **v0.2** — voting bulletins (done), real places in addresses (done)
- **v0.3** — more types: boleto, payslip (holerite), receipt (cupom fiscal), official gazette tables (Diário Oficial)
- **v0.4** — handwriting: filled forms, medical prescriptions
