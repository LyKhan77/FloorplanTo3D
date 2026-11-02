"""Perforated tray sheet (M12b): one 25 x 25 mm cell with a 7 x 20 mm slot, tiled by the builder's box UVs.
The metal colour is baked into the tile, so the material reads Base Color and Alpha straight from it."""

from pathlib import Path

import cv2
import numpy as np

PX_PER_MM = 2
CELL_MM = 25
SLOT_MM = (7, 20)  # across, along


def write_perforation_png(path: Path, color: str) -> Path:
    h = color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    n = CELL_MM * PX_PER_MM
    img = np.zeros((n, n, 4), np.uint8)
    img[..., :3] = (b, g, r)
    img[..., 3] = 255
    sw, sh = SLOT_MM[0] * PX_PER_MM, SLOT_MM[1] * PX_PER_MM
    x0, y0 = (n - sw) // 2, (n - sh) // 2
    img[y0:y0 + sh, x0:x0 + sw] = (24, 24, 24, 0)  # dark under the alpha: a viewer that draws the sheet solid still shows holes
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(path), img)
    return Path(path)
