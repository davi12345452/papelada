# papelada

**How well do AI models read Brazilian documents — and do they make things up when they can't?**

`papelada` (Portuguese for *paperwork*) is an open benchmark for structured data extraction from Brazilian documents: invoices, PIX receipts, voting bulletins and more. Models receive a document image and a JSON schema, and must return the data — or `null` when a field isn't there.

Most document benchmarks are English and US-centric. Brazilian paperwork has its own formats (CNPJ, CPF, `R$ 1.234,56`, NF-e access keys) and its own failure modes. This project measures them.

## What it measures

- **Field accuracy** — after normalization, so `123.456.789-09` and `12345678909` are the same CPF. Format errors and value errors are reported separately.
- **Table accuracy** — cell-level scoring for line items and tabular sections.
- **Hallucination rate** — the model fills a field that does not exist in the document. This is the headline metric.
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
uv run papelada generate pix_receipt --n 12 --seed 0 --out data/sample
uv run pytest
```

## Status

Early design. The PIX receipt generator works; DANFE and voting bulletins are next. See [docs/PLAN.md](docs/PLAN.md) for methodology and roadmap, and [`schemas/`](schemas/) for the extraction targets.
