# papelada

**How well do AI models read Brazilian documents — and do they make things up when they can't?**

`papelada` (Portuguese for *paperwork*) is an open benchmark for structured data extraction from Brazilian documents: PIX receipts, invoices (DANFE) and voting bulletins. Models receive a document image and a JSON schema, and must return the data — or `null` when a field isn't there.

Most document benchmarks are English and US-centric. Brazilian paperwork has its own formats (CNPJ, CPF, `R$ 1.234,56`, NF-e access keys, boletim de urna) and its own failure modes. This project measures them.

## Latest results

Seven cheap, recent models via OpenRouter, October 2026. Accuracy per field; L0 is a clean render, L1 a scan, L2 a phone photo.

| Model | PIX | DANFE L0 / L1 / L2 | Bulletin L0 / L1 / L2 | US$/doc |
|---|---|---|---|---|
| `anthropic/claude-haiku-5.5` | 99.5 | 100.0 / 99.8 / **97.2** | 99.5 / 96.8 / 92.0 | 0.0016 |
| `openai/gpt-6-luna` | 98.6 | 99.7 / 99.4 / 84.8 | 99.5 / 98.6 / 96.9 | **0.0011** |
| `qwen/qwen3.8-27b` | 98.0 | 95.9 / 96.6 / 82.7 | 99.8 / 99.8 / **98.7** | 0.0039 |
| `deepseek/deepseek-v4.1-flash-1017` | 99.0 | 99.5 / 99.2 / 81.2 | 99.3 / 99.4 / 95.8 | 0.0023 |
| `minimax/minimax-m3.1-flash` | 98.9 | 99.2 / 96.4 / 80.1 | 97.9 / 86.9 / 89.7 | 0.0042 |
| `nvidia/nemotron-3.5-super-vl` | 98.0 | 98.6 / 98.3 / 82.3 | 97.7 / 92.9 / 81.8 | 0.0032 |
| `xiaomi/mimo-v2.6-flash` | 99.1 | 98.3 / 88.3 / 62.5 | 99.6 / 92.2 / 82.7 | 0.0028 |

What stands out: no model wins everything; clean documents are solved, photos are not; no model invented a value for an absent field, but under degradation models replace unreadable words with plausible real ones ("Pereira" → "Pirenópolis") and confuse Portuguese accents on uppercase print ("TETÊ" → "TETÉ"). Small samples — read [the full write-up](docs/results-2026-10-28.md) before drawing conclusions.

## What it measures

- **Field accuracy** — after normalization, so `123.456.789-09` and `12345678909` are the same CPF.
- **Table accuracy** — cell-level scoring for invoice items and bulletin candidates, with rows paired by content.
- **Hallucination** — the model fills a field that does not exist in the document with something not printed anywhere on it.
- **Misattribution** — the model copies real text from the wrong place: a footer into the description, the payer's CPF into the payee's field.
- **Substitution** — the model could not read a word and wrote a different real word or place instead.
- **Trap accuracy** — text a model is tempted to "fix": uncommon name spellings (Thyago, Uóxinton), homophones (conserto/concerto), typos, slang and ballot nicknames as they are actually printed.
- **Schema validity**, **cost** and **latency** per document.

## How it works

Documents are **synthetic**: rendered from templates with fake but valid data (correct check digits, NF-e access keys, totals and vote counts that add up), then degraded across three levels — clean render, scan, phone photo. Every document is rendered at all three levels, so the effect of degradation is measured on the same content. Synthetic data gives perfect ground truth, keeps personal data out of the dataset, and lets fresh test sets be generated so models can't memorize them.

[`samples/`](samples/) has a few public examples of each document type, with their images, gold JSON and metadata.

Methodology, scoring rules and roadmap: [docs/PLAN.md](docs/PLAN.md). Extraction targets: [`schemas/`](schemas/).

## Open, but not leakable

Everything is reproducible from a seed, so the code alone could regenerate any test set. Published results use seeds that are disclosed with them; future scored sets use undisclosed seeds, and only samples are published. Free (`:free`) model endpoints, which may train on inputs, are never used on a private set.

## Usage

Requires [uv](https://docs.astral.sh/uv/).

```sh
uv sync
uv run papelada generate pix_receipt --n 24 --seed 0 --out data/sample
uv run papelada generate danfe --n 12 --seed 0 --out data/sample
uv run papelada generate voting_bulletin --n 12 --seed 0 --out data/sample
uv run papelada fetch-lexicon   # word and place lists for the substitution metric

# Models are "<provider>:<model id>". Keys come from the environment or a gitignored .env:
# openrouter (OPENROUTER_API_KEY), google (GOOGLE_API_KEY)
uv run papelada run openrouter:deepseek/deepseek-v4.1-flash-1017 --data data/sample
uv run papelada report results/runs/*.jsonl --fields

# Scoring changes can be applied to saved runs without calling models again
uv run papelada rescore results/runs/*.jsonl

uv run pytest
```

## Status

Early and opinionated. Three document types, one prompt, small samples. Planned: a handful of real public documents (TSE bulletins) as a realism check, larger samples, more document types (boleto, payslip, receipts), and handwriting.

## Data sources

- Municipalities: [IBGE localities API](https://servicodados.ibge.gov.br/api/docs/localidades), public data, vendored in `src/papelada/data/municipalities.csv`.
- Word frequencies for the substitution metric: [FrequencyWords](https://github.com/hermitdave/FrequencyWords) by Hermit Dave (CC BY-SA 4.0), downloaded on demand, not redistributed.
- Names, companies and streets in generated documents are fake (Faker `pt_BR` and fixed lists). Institutions on PIX receipts, and parties and candidates on voting bulletins, are fictional.

## License

Code under the [MIT License](LICENSE). Generated samples in [`samples/`](samples/) under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
