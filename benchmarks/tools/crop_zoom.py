"""Measuring aid: zoomed crop with pixel ticks (every 10 px) and labels (every 50 px).

Usage: uv run python -m benchmarks.tools.crop_zoom <image> x0 y0 x1 y1 [--scale 4] [--out PATH]
"""

import argparse
import tempfile
from pathlib import Path

import cv2
import numpy as np

MARGIN = 44


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("image", type=Path)
    ap.add_argument("box", type=int, nargs=4, metavar=("X0", "Y0", "X1", "Y1"))
    ap.add_argument("--scale", type=int, default=4)
    ap.add_argument("--out", type=Path, default=Path(tempfile.gettempdir()) / "crop_zoom.png")
    a = ap.parse_args(argv)
    x0, y0, x1, y1 = a.box
    crop = cv2.imread(str(a.image))[y0:y1, x0:x1]
    big = cv2.resize(crop, None, fx=a.scale, fy=a.scale, interpolation=cv2.INTER_NEAREST)
    canvas = np.full((big.shape[0] + MARGIN, big.shape[1] + MARGIN, 3), 255, np.uint8)
    canvas[MARGIN:, MARGIN:] = big
    for x in range(x0 - x0 % 10, x1 + 1, 10):
        if x < x0:
            continue
        cx = MARGIN + (x - x0) * a.scale
        major = x % 50 == 0
        cv2.line(canvas, (cx, MARGIN - (14 if major else 6)), (cx, MARGIN), (0, 0, 255), 1)
        if major:
            cv2.putText(canvas, str(x), (cx + 2, 14), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 200), 1)
    for y in range(y0 - y0 % 10, y1 + 1, 10):
        if y < y0:
            continue
        cy = MARGIN + (y - y0) * a.scale
        major = y % 50 == 0
        cv2.line(canvas, (MARGIN - (14 if major else 6), cy), (MARGIN, cy), (0, 0, 255), 1)
        if major:
            cv2.putText(canvas, str(y), (2, cy - 2), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 0, 200), 1)
    cv2.imwrite(str(a.out), canvas)
    print(a.out)


if __name__ == "__main__":
    main()
