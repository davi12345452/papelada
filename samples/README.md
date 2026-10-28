# Samples

Public examples generated with seeds from 900000, one per PIX layout plus a DANFE and two voting bulletins (first and second round). They are not part of any scored set.

Each folder holds:

- `L0.png`, `L1.jpg`, `L2.jpg` — the same document as a clean render, a scan and a phone photo
- `gold.json` — the extraction target, valid against the schema in `schemas/`
- `meta.json` — seed, layout, generator version, absent fields, trap fields and every string printed on the page

Regenerate any of them with `uv run papelada generate <doc type> --n 1 --seed <seed> --out samples`.

Licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
