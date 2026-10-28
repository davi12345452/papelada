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

- Multimodal LLMs via a single gateway (OpenRouter), same prompt, temperature 0, schema in the prompt.
- Focus on **recent, cheap, open-weight models, plus two cheap closed references**: the ones you'd actually run on thousands of documents. Lineup is refreshed as new models ship. v0 (OpenRouter IDs, release date on OpenRouter, USD per 1M input/output tokens, Oct 2026):

| Model | Released | Open weights | Price in/out |
|---|---|---|---|
| `minimax/minimax-m3.1-flash` | 2026-10-19 | to verify | 0.15 / 0.60 |
| `deepseek/deepseek-v4.1-flash-1017` | 2026-10-17 | to verify | 0.15 / 0.60 |
| `nvidia/nemotron-3.5-super-vl` | 2026-10-15 | reported | 0.15 / 0.50 |
| `xiaomi/mimo-v2.6-flash` | 2026-09-21 | to verify | 0.14 / 0.28 |
| `qwen/qwen3.8-27b` | 2026-08-14 | to verify (vision weights) | 0.039 / 1.25 |
| `openai/gpt-6-luna` | 2026-09-22 | no, cheap closed reference | 0.10 / 0.50 |
| `anthropic/claude-haiku-5.5` | 2026-10-07 | no, cheap closed reference | 0.10 / 0.50 |

- Dedicated OCR models (PaddleOCR-VL, GLM-OCR, MinerU) lead OmniDocBench but aren't on OpenRouter; they belong with the classic-pipeline baselines.
- Free (`:free`) endpoints may let the provider train on inputs. They are fine for the public sample, never for the private scored set.
- Classic pipelines as baselines: Tesseract + LLM, Docling + LLM.
- Each sample is run 3× for models without deterministic output; variance is reported.

## Contamination policy

- Public: harness, generator, methodology, results, and a ~10% sample of the test set.
- Private: the scored test set, regenerated with new seeds each release.
- Real-world documents only from public sources (e.g. TSE bulletins); never personal documents.

## Open decisions

- [x] Language for generator and harness: Python (managed with uv)
- [ ] Bundle open-licensed fonts so renders are pixel-identical across machines
- [ ] License (MIT for code; dataset license TBD)
- [ ] Results format and leaderboard page

## Roadmap

- **v0** — 3 document types, 3 levels, first results
- **v1** — more types: boleto, payslip (holerite), receipt (cupom fiscal), official gazette tables (Diário Oficial)
- **v2** — handwriting: filled forms, medical prescriptions
