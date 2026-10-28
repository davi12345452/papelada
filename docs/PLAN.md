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
2. HTML/CSS templates per document type (several layouts per type — PIX receipts vary per bank) rendered to image with a headless browser.
3. Degradation via [Augraphy](https://github.com/sparkfish/augraphy) or equivalent.
4. Each sample is saved as `image.png` + `gold.json` + `meta.json` (type, layout, level, seed).

Every sample is reproducible from its seed.

### Optional fields

To measure hallucination, each layout randomly omits optional fields (e.g. PIX description, payer document, freight). The gold value becomes `null`, and any non-null prediction counts as a hallucination.

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
| value | different value | wrong |
| value | `null` | omission |
| `null` | `null` | correct |
| `null` | value | **hallucination** |

Tables are scored cell by cell after aligning rows (by order, falling back to best match on description). Missing and extra rows are counted separately.

Reported per model: field accuracy, hallucination rate, omission rate, table cell F1, schema validity on first try, cost per document, p50/p95 latency. All metrics are also broken down by document type and degradation level.

## Models and baselines

- Multimodal LLMs via a single gateway (OpenRouter), same prompt, temperature 0, schema in the prompt and via structured output when supported.
- Classic pipelines as baselines: Tesseract + LLM, Docling + LLM.
- Each sample is run 3× for models without deterministic output; variance is reported.

## Contamination policy

- Public: harness, generator, methodology, results, and a ~10% sample of the test set.
- Private: the scored test set, regenerated with new seeds each release.
- Real-world documents only from public sources (e.g. TSE bulletins); never personal documents.

## Open decisions

- [ ] Language for generator and harness (Python fits the tooling: Faker `pt_BR`, Augraphy, validate-docbr)
- [ ] License (MIT for code; dataset license TBD)
- [ ] Results format and leaderboard page

## Roadmap

- **v0** — 3 document types, 3 levels, first results
- **v1** — more types: boleto, payslip (holerite), receipt (cupom fiscal), official gazette tables (Diário Oficial)
- **v2** — handwriting: filled forms, medical prescriptions
