#!/usr/bin/env python3
"""Compare two rendered EXRs and optionally write a visual diff image."""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import numpy as np


def load_exr(path: str) -> np.ndarray:
    try:
        import OpenEXR
        import Imath
    except ImportError:
        return load_exr_with_mitsuba(path)

    exr = OpenEXR.InputFile(path)
    header = exr.header()
    data_window = header["dataWindow"]
    width = data_window.max.x - data_window.min.x + 1
    height = data_window.max.y - data_window.min.y + 1
    pixel_type = Imath.PixelType(Imath.PixelType.FLOAT)

    channel_names = header["channels"].keys()
    required = ["R", "G", "B"]
    if not all(name in channel_names for name in required):
        raise RuntimeError(f"{path} is missing one of the channels {required}")

    channels = [
        np.frombuffer(exr.channel(name, pixel_type), dtype=np.float32).reshape(height, width)
        for name in required
    ]
    return np.stack(channels, axis=-1)


def load_exr_with_mitsuba(path: str) -> np.ndarray:
    try:
        import mitsuba as mi
    except ImportError as exc:
        raise RuntimeError(
            "Need either OpenEXR/Imath or Mitsuba installed to read EXR files."
        ) from exc

    mi.set_variant("scalar_rgb")
    bitmap = mi.Bitmap(str(path)).convert(
        mi.Bitmap.PixelFormat.RGB,
        mi.Struct.Type.Float32,
        srgb_gamma=False,
    )
    return np.array(bitmap, copy=False)


def compute_metrics(image_a: np.ndarray, image_b: np.ndarray) -> dict[str, float]:
    diff = image_a - image_b
    abs_diff = np.abs(diff)

    mse = float(np.mean(diff * diff))
    rmse = math.sqrt(mse)
    mae = float(np.mean(abs_diff))
    max_error = float(np.max(abs_diff))

    return {
        "rmse": rmse,
        "mae": mae,
        "max_error": max_error,
    }


def describe_invalid_values(image: np.ndarray) -> str | None:
    non_finite_mask = ~np.isfinite(image)
    if not np.any(non_finite_mask):
        return None

    invalid_count = int(np.count_nonzero(non_finite_mask))
    nan_count = int(np.count_nonzero(np.isnan(image)))
    posinf_count = int(np.count_nonzero(np.isposinf(image)))
    neginf_count = int(np.count_nonzero(np.isneginf(image)))
    return (
        f"{invalid_count} non-finite values "
        f"({nan_count} NaN, {posinf_count} +Inf, {neginf_count} -Inf)"
    )


def validate_finite_image(label: str, image: np.ndarray) -> str | None:
    detail = describe_invalid_values(image)
    if detail is None:
        return None
    return f"{label} contains {detail}"


def validate_finite_metrics(metrics: dict[str, float]) -> list[str]:
    failures = []
    for name, value in metrics.items():
        if not math.isfinite(value):
            failures.append(f"metric '{name}' is non-finite: {value!r}")
    return failures


def print_image_summary(label: str, image: np.ndarray) -> None:
    invalid_detail = describe_invalid_values(image)
    if invalid_detail is None:
        print(
            f"Loaded {label}: shape={image.shape}, "
            f"range=[{image.min():.6f}, {image.max():.6f}]"
        )
        return

    print(
        f"Loaded {label}: shape={image.shape}, "
        f"invalid={invalid_detail}"
    )


def tonemap_aces(image: np.ndarray) -> np.ndarray:
    a = 2.51
    b = 0.03
    c = 2.43
    d = 0.59
    e = 0.14
    mapped = (image * (a * image + b)) / (image * (c * image + d) + e)
    return np.clip(mapped, 0.0, 1.0)


def linear_to_srgb(image: np.ndarray) -> np.ndarray:
    return np.where(
        image <= 0.0031308,
        image * 12.92,
        1.055 * np.power(np.clip(image, 0.0031308, None), 1.0 / 2.4) - 0.055,
    )


def write_comparison_image(
    image_a: np.ndarray,
    image_b: np.ndarray,
    output: str,
    error_scale: float,
) -> None:
    try:
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError("Pillow is required to write a comparison image.") from exc

    diff = np.abs(image_a - image_b) * error_scale
    combined = np.concatenate(
        [
            tonemap_aces(image_a),
            tonemap_aces(image_b),
            np.clip(diff, 0.0, 1.0),
        ],
        axis=1,
    )
    srgb = linear_to_srgb(combined)
    rgb8 = np.clip(srgb * 255.0, 0.0, 255.0).astype(np.uint8)
    Image.fromarray(rgb8, mode="RGB").save(output)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Compare two EXR renders and report absolute error metrics."
    )
    parser.add_argument("image_a", help="First EXR, typically the Flux render.")
    parser.add_argument("image_b", help="Second EXR, typically the Mitsuba render.")
    parser.add_argument(
        "--comparison-output",
        help="Optional PNG path for a tonemapped side-by-side comparison image.",
    )
    parser.add_argument(
        "--error-scale",
        type=float,
        default=8.0,
        help="Scale factor applied to the absolute-error visualization.",
    )
    parser.add_argument(
        "--rmse-threshold",
        type=float,
        help="Fail if RMSE exceeds this value.",
    )
    parser.add_argument(
        "--mae-threshold",
        type=float,
        help="Fail if MAE exceeds this value.",
    )
    parser.add_argument(
        "--max-threshold",
        type=float,
        help="Fail if max absolute error exceeds this value.",
    )
    return parser.parse_args()


def check_threshold(name: str, value: float, threshold: float | None) -> str | None:
    if threshold is None:
        return None
    if value > threshold:
        return f"{name}={value:.6f} exceeds threshold {threshold:.6f}"
    return None


def main():
    args = parse_args()

    try:
        image_a = load_exr(args.image_a)
        image_b = load_exr(args.image_b)
    except Exception as exc:
        print(f"FAIL: could not load EXR input: {exc}", file=sys.stderr)
        return 2

    print_image_summary(Path(args.image_a).name, image_a)
    print_image_summary(Path(args.image_b).name, image_b)

    if image_a.shape != image_b.shape:
        print(
            f"Shape mismatch: {image_a.shape} vs {image_b.shape}",
            file=sys.stderr,
        )
        return 2

    input_failures = [
        validate_finite_image(Path(args.image_a).name, image_a),
        validate_finite_image(Path(args.image_b).name, image_b),
    ]
    input_failures = [failure for failure in input_failures if failure]
    if input_failures:
        for failure in input_failures:
            print(f"FAIL: {failure}", file=sys.stderr)
        return 1

    metrics = compute_metrics(image_a, image_b)
    metric_failures = validate_finite_metrics(metrics)
    if metric_failures:
        for failure in metric_failures:
            print(f"FAIL: {failure}", file=sys.stderr)
        return 1

    print(f"RMSE:      {metrics['rmse']:.6f}")
    print(f"MAE:       {metrics['mae']:.6f}")
    print(f"Max error: {metrics['max_error']:.6f}")

    if args.comparison_output:
        try:
            write_comparison_image(
                image_a,
                image_b,
                args.comparison_output,
                error_scale=args.error_scale,
            )
        except Exception as exc:
            print(f"FAIL: could not write comparison image: {exc}", file=sys.stderr)
            return 2
        print(f"Wrote comparison image: {args.comparison_output}")

    failures = [
        check_threshold("rmse", metrics["rmse"], args.rmse_threshold),
        check_threshold("mae", metrics["mae"], args.mae_threshold),
        check_threshold("max_error", metrics["max_error"], args.max_threshold),
    ]
    failures = [failure for failure in failures if failure]
    if failures:
        for failure in failures:
            print(f"FAIL: {failure}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
