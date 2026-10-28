# papelada

**How well do AI models read Brazilian documents — and do they make things up when they can't?**

`papelada` (Portuguese for *paperwork*) is an open benchmark for structured data extraction from Brazilian documents: invoices, PIX receipts, voting bulletins and more. Models receive a document image and a JSON schema, and must return the data — or `null` when a field isn't there.

Most document benchmarks are English and US-centric. Brazilian paperwork has its own formats (CNPJ, CPF, `R$ 1.234,56`, NF-e access keys) and its own failure modes. This project measures them.

## What it measures

- **Field accuracy** — after normalization, so `123.456.789-09` and `12345678909` are the same CPF.
- **Table accuracy** — cell-level scoring for invoice line items.
- **Hallucination rate** — the model fills a field that does not exist in the document with something not printed anywhere on it. This is the headline metric.
- **Misattribution** — the model copies real text from the wrong place: a footer into the description, the payer's CPF into the payee's field.
- **Trap accuracy** — text a model is tempted to "fix": uncommon name spellings (Thyago, Uóxinton), homophones (conserto/concerto), typos and slang as people actually type them.
- **Schema validity** — valid JSON matching the schema on the first try.
- **Cost and latency** per document.

## How it works

Documents are **synthetic**: rendered from templates with fake but valid data (correct check digits, consistent totals), then degraded across difficulty levels — clean render, scan, phone photo. This gives perfect ground truth, keeps personal data out of the dataset, and lets us regenerate fresh test sets so models can't memorize them.

A small set of real public documents (e.g. voting bulletins published by TSE) serves as a realism check.

## Open, but not leakable

The harness, methodology, generator and results are public. Only a sample of the scored test set is published; the rest stays private and is regenerated periodically.

## Usage

Requires [uv](https://docs.astral.sh/uv/).

```sh
uv sync
uv run papelada generate pix_receipt --n 24 --seed 0 --out data/sample
uv run papelada generate danfe --n 12 --seed 0 --out data/sample
uv run papelada fetch-lexicon   # word and place lists for the substitution metric

# Models are "<provider>:<model id>". Keys come from the environment or a gitignored .env:
# openrouter (OPENROUTER_API_KEY), google (GOOGLE_API_KEY)
uv run papelada run openrouter:deepseek/deepseek-v4.1-flash-1017 --data data/sample
uv run papelada report results/runs/*.jsonl --fields

uv run pytest
```

## Status

Early. Generators for PIX receipts and DANFE, the runner and the scoring work; first results in [docs/results-2026-10-28.md](docs/results-2026-10-28.md). Voting bulletins are next. See [docs/PLAN.md](docs/PLAN.md) for methodology and roadmap, and [`schemas/`](schemas/) for the extraction targets.
