"""Safely crop a single card from a flatbed scanner image.

If detection is uncertain we preserve the original image and request review
rather than aggressively cropping away serial numbering or borders.
"""
from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO

import cv2
import numpy as np
from PIL import Image, ImageOps


@dataclass
class CropResult:
    image: Image.Image
    needs_review: bool
    reason: str
    confidence: float


def open_scan(data: bytes) -> Image.Image:
    with Image.open(BytesIO(data)) as im:
        return ImageOps.exif_transpose(im).convert("RGB")


def _order_corners(points: np.ndarray) -> np.ndarray:
    """Consistent top-left, top-right, bottom-right, bottom-left order."""
    points = np.asarray(points, dtype=np.float32)
    sums = points.sum(axis=1)
    diffs = np.diff(points, axis=1).ravel()
    return np.array([
        points[np.argmin(sums)],
        points[np.argmin(diffs)],
        points[np.argmax(sums)],
        points[np.argmax(diffs)],
    ], dtype=np.float32)


def crop_card(image: Image.Image) -> CropResult:
    image = ImageOps.exif_transpose(image).convert("RGB")
    rgb = np.asarray(image)
    h, w = rgb.shape[:2]
    if min(h, w) < 160:
        return CropResult(image, True, "Image too small for safe auto-cropping", 0.0)

    pad = max(2, int(min(h, w) * .025))
    corner = max(4, int(min(h, w) * .04))
    samples = np.concatenate([
        rgb[:corner, :corner].reshape(-1, 3),
        rgb[:corner, -corner:].reshape(-1, 3),
        rgb[-corner:, :corner].reshape(-1, 3),
        rgb[-corner:, -corner:].reshape(-1, 3),
    ]).astype(np.float32)
    background = np.median(samples, axis=0)
    spread = np.median(np.linalg.norm(samples - background, axis=1))
    if spread > 35:
        return CropResult(image, True, "Scanner background is inconsistent", 0.0)

    distance = np.linalg.norm(rgb.astype(np.float32) - background, axis=2)
    mask = np.uint8(distance > max(28., spread * 3.0)) * 255
    mask[:pad, :] = 0
    mask[-pad:, :] = 0
    mask[:, :pad] = 0
    mask[:, -pad:] = 0
    kernel_size = max(3, int(min(h, w) * .008) | 1)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (kernel_size, kernel_size))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return CropResult(image, True, "Card edges not detected", 0.0)
    contour = max(contours, key=cv2.contourArea)
    area_ratio = cv2.contourArea(contour) / (w * h)
    if not .02 <= area_ratio <= .9:
        return CropResult(image, True, "Detected region is not a reliable card", 0.0)

    rect = cv2.minAreaRect(contour)
    rw, rh = rect[1]
    if rw < 50 or rh < 50:
        return CropResult(image, True, "Card region too small", 0.0)
    aspect = min(rw, rh) / max(rw, rh)
    if not .57 <= aspect <= .84:
        return CropResult(image, True, "Unusual aspect ratio; manually verify crop", 0.0)

    vertices = _order_corners(cv2.boxPoints(rect))
    top = np.linalg.norm(vertices[0] - vertices[1])
    bottom = np.linalg.norm(vertices[2] - vertices[3])
    left = np.linalg.norm(vertices[0] - vertices[3])
    right = np.linalg.norm(vertices[1] - vertices[2])
    out_w = max(1, int(round(max(top, bottom))))
    out_h = max(1, int(round(max(left, right))))
    target = np.array([[0, 0], [out_w - 1, 0], [out_w - 1, out_h - 1], [0, out_h - 1]], dtype=np.float32)
    transform = cv2.getPerspectiveTransform(vertices, target)
    warped = cv2.warpPerspective(rgb, transform, (out_w, out_h), flags=cv2.INTER_CUBIC)
    if out_w > out_h:
        warped = cv2.rotate(warped, cv2.ROTATE_90_CLOCKWISE)
    confidence = max(0., min(.96, .85 - abs(aspect - (2.5 / 3.5)) * 2))
    return CropResult(
        Image.fromarray(warped), confidence < .74,
        "Auto-crop: inspect all four edges" if confidence < .74 else "Auto-crop detected",
        confidence,
    )
