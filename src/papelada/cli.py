"""papelada command line.

    papelada generate pix_receipt --n 12 --seed 0 --out data/sample
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from jsonschema import Draft202012Validator

from papelada import GENERATOR_VERSION
from papelada.degrade import LEVELS, degrade
from papelada.doctypes import DOC_TYPES

SCHEMAS_DIR = Path(__file__).resolve().parents[2] / "schemas"


def validator(doc_type: str) -> Draft202012Validator:
    schema = json.loads((SCHEMAS_DIR / f"{doc_type}.schema.json").read_text())
    return Draft202012Validator(schema)


def generate(doc_type: str, n: int, seed: int, out: Path, levels: list[str]) -> None:
    module = DOC_TYPES[doc_type]
    check = validator(doc_type)
    for sample_seed in range(seed, seed + n):
        sample = module.generate(sample_seed)
        errors = sorted(check.iter_errors(sample.gold), key=str)
        if errors:
            raise ValueError(f"seed {sample_seed}: gold does not match schema: {errors[0].message}")

        sample_dir = out / doc_type / f"{doc_type}-{sample_seed:06d}"
        sample_dir.mkdir(parents=True, exist_ok=True)
        images = {}
        for level in levels:
            rng = np.random.default_rng([sample_seed, LEVELS.index(level)])
            image = degrade(sample.image, level, rng)
            # Degraded levels already carry JPEG artifacts; store them as high-quality JPEG.
            if level == "L0":
                name = "L0.png"
                image.save(sample_dir / name)
            else:
                name = f"{level}.jpg"
                image.save(sample_dir / name, quality=92)
            images[level] = name

        meta = {**sample.meta, "generator_version": GENERATOR_VERSION, "images": images}
        (sample_dir / "gold.json").write_text(json.dumps(sample.gold, ensure_ascii=False, indent=2) + "\n")
        (sample_dir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n")
        print(f"{sample_dir}  layout={sample.meta['layout']}")


def main() -> None:
    parser = argparse.ArgumentParser(prog="papelada")
    sub = parser.add_subparsers(dest="command", required=True)

    gen = sub.add_parser("generate", help="generate synthetic samples")
    gen.add_argument("doc_type", choices=sorted(DOC_TYPES))
    gen.add_argument("--n", type=int, default=10)
    gen.add_argument("--seed", type=int, default=0, help="first sample seed; samples use seed..seed+n-1")
    gen.add_argument("--out", type=Path, default=Path("data/sample"))
    gen.add_argument("--levels", default=",".join(LEVELS))

    args = parser.parse_args()
    if args.command == "generate":
        levels = args.levels.split(",")
        unknown = set(levels) - set(LEVELS)
        if unknown:
            parser.error(f"unknown levels: {', '.join(sorted(unknown))}")
        generate(args.doc_type, args.n, args.seed, args.out, levels)


if __name__ == "__main__":
    main()
