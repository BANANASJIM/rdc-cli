"""Pixel-level image comparison utility."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image


@dataclass(frozen=True)
class CompareResult:
    """Result of comparing two images pixel-by-pixel."""

    identical: bool
    diff_pixels: int
    total_pixels: int
    diff_ratio: float
    diff_image: Path | None


def compare_images(
    path_a: Path,
    path_b: Path,
    threshold: float = 0.0,
    diff_output: Path | None = None,
) -> CompareResult:
    """Compare two images pixel-by-pixel.

    Args:
        path_a: Path to the first (expected) image.
        path_b: Path to the second (actual) image.
        threshold: Maximum diff ratio (%) to still count as identical.
        diff_output: If set, write a diff visualization PNG here.

    Returns:
        CompareResult with comparison details.

    Raises:
        ValueError: If the two images have different dimensions.
        FileNotFoundError: If either path does not exist.
        PIL.UnidentifiedImageError: If either file is not a valid image.
    """
    img_a = Image.open(path_a).convert("RGBA")
    img_b = Image.open(path_b).convert("RGBA")

    if img_a.size != img_b.size:
        raise ValueError(f"size mismatch: {img_a.size} vs {img_b.size}")

    arr_a = np.array(img_a, dtype=np.uint8)
    arr_b = np.array(img_b, dtype=np.uint8)

    mask = np.any(arr_a != arr_b, axis=2)
    diff_pixels = int(np.count_nonzero(mask))
    total_pixels = img_a.size[0] * img_a.size[1]
    diff_ratio = diff_pixels / total_pixels * 100.0
    identical = diff_ratio <= threshold

    diff_image: Path | None = None
    if diff_output and diff_pixels > 0:
        gray = img_a.convert("L").convert("RGBA")
        diff_arr = np.array(gray, dtype=np.uint8)
        diff_arr[mask] = [255, 0, 0, 255]
        Image.fromarray(diff_arr).save(diff_output)
        diff_image = diff_output

    return CompareResult(
        identical=identical,
        diff_pixels=diff_pixels,
        total_pixels=total_pixels,
        diff_ratio=diff_ratio,
        diff_image=diff_image,
    )
