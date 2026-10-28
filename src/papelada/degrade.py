"""Degradation levels applied to a clean render.

L0  clean render
L1  scan: small rotation, paper tint, softness, noise, JPEG artifacts
L2  phone photo: perspective, background, uneven light, shadow, blur, downscale, noise, JPEG
"""

from __future__ import annotations

import io

import numpy as np
from PIL import Image, ImageEnhance, ImageFilter

LEVELS = ("L0", "L1", "L2")


def degrade(img: Image.Image, level: str, rng: np.random.Generator) -> Image.Image:
    if level == "L0":
        return img
    if level == "L1":
        return _scan(img, rng)
    if level == "L2":
        return _photo(img, rng)
    raise ValueError(f"Unknown level: {level}")


def _scan(img: Image.Image, rng: np.random.Generator) -> Image.Image:
    tint = np.array([rng.uniform(0.95, 0.99), rng.uniform(0.94, 0.98), rng.uniform(0.90, 0.96)])
    img = _multiply(img, tint)
    img = img.rotate(rng.uniform(-3, 3), resample=Image.BICUBIC, expand=True, fillcolor=(242, 240, 232))
    img = ImageEnhance.Contrast(img).enhance(rng.uniform(0.82, 0.95))
    img = img.filter(ImageFilter.GaussianBlur(rng.uniform(0.3, 0.7)))
    img = _noise(img, rng.uniform(4, 8), rng)
    return _jpeg(img, int(rng.integers(55, 76)))


def _photo(img: Image.Image, rng: np.random.Generator) -> Image.Image:
    w, h = img.size
    pad = int(0.08 * max(w, h))
    table = tuple(int(c) for c in rng.integers([70, 60, 45], [140, 120, 100]))
    canvas = Image.new("RGB", (w + 2 * pad, h + 2 * pad), table)
    canvas.paste(img, (pad, pad))

    # Tilt the document: move each corner of the paper by a random amount.
    cw, ch = canvas.size
    paper = [(pad, pad), (pad + w, pad), (pad + w, pad + h), (pad, pad + h)]
    jitter = 0.05 * np.array([w, h])
    tilted = [tuple(np.array(p) + rng.uniform(-1, 1, 2) * jitter) for p in paper]
    coeffs = _perspective_coeffs(tilted, paper)
    canvas = canvas.transform((cw, ch), Image.PERSPECTIVE, coeffs, Image.BICUBIC, fillcolor=table)

    canvas = _lighting(canvas, rng)
    canvas = canvas.filter(ImageFilter.GaussianBlur(rng.uniform(0.8, 1.6)))
    scale = rng.uniform(0.55, 0.75)
    canvas = canvas.resize((int(cw * scale), int(ch * scale)), Image.LANCZOS)
    canvas = _noise(canvas, rng.uniform(6, 12), rng)
    return _jpeg(canvas, int(rng.integers(40, 66)))


def _lighting(img: Image.Image, rng: np.random.Generator) -> Image.Image:
    w, h = img.size
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    xs /= w
    ys /= h

    # Light falls off along a random direction.
    angle = rng.uniform(0, 2 * np.pi)
    t = (np.cos(angle) * (xs - 0.5) + np.sin(angle) * (ys - 0.5)) + 0.5
    low = rng.uniform(0.6, 0.8)
    factor = low + (1 - low) * np.clip(t, 0, 1)

    # Soft-edged shadow over part of the frame (a hand or the phone).
    shadow_angle = rng.uniform(0, 2 * np.pi)
    s = np.cos(shadow_angle) * (xs - 0.5) + np.sin(shadow_angle) * (ys - 0.5)
    edge = rng.uniform(0.1, 0.4)
    factor *= 1 - rng.uniform(0.15, 0.3) / (1 + np.exp(-(s - edge) / 0.03))

    # Vignette.
    factor *= 1 - 0.25 * ((xs - 0.5) ** 2 + (ys - 0.5) ** 2)

    arr = np.asarray(img, dtype=np.float32) * factor[..., None]
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))


def _perspective_coeffs(output_pts, input_pts) -> list[float]:
    """Coefficients for Image.PERSPECTIVE mapping output pixels back to input pixels."""
    a, b = [], []
    for (x, y), (u, v) in zip(output_pts, input_pts):
        a.append([x, y, 1, 0, 0, 0, -u * x, -u * y])
        a.append([0, 0, 0, x, y, 1, -v * x, -v * y])
        b.extend([u, v])
    return np.linalg.solve(np.array(a, dtype=np.float64), np.array(b, dtype=np.float64)).tolist()


def _multiply(img: Image.Image, factor: np.ndarray) -> Image.Image:
    arr = np.asarray(img, dtype=np.float32) * factor
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))


def _noise(img: Image.Image, sigma: float, rng: np.random.Generator) -> Image.Image:
    arr = np.asarray(img, dtype=np.float32)
    arr = arr + rng.normal(0, sigma, arr.shape)
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))


def _jpeg(img: Image.Image, quality: int) -> Image.Image:
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=quality)
    buf.seek(0)
    return Image.open(buf).convert("RGB")
