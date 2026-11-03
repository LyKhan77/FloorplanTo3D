import base64

import cv2
import numpy as np


def _pdf(pages: int) -> bytes:
    import pymupdf as fitz

    doc = fitz.open()
    for i in range(pages):
        page = doc.new_page(width=600, height=400)
        page.draw_rect(fitz.Rect(50, 50, 550, 350))
        page.insert_text((60, 80), f"page {i + 1}")
    return doc.tobytes()


def _png(data_url: str) -> np.ndarray:
    raw = base64.b64decode(data_url.split(",", 1)[1])
    return cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)


def test_pdf_pages_returns_thumbnails(client):
    r = client.post("/api/pdf/pages", files={"file": ("a.pdf", _pdf(3), "application/pdf")})
    assert r.status_code == 200
    body = r.json()
    assert body["page_count"] == 3 and [p["page"] for p in body["pages"]] == [1, 2, 3]
    thumb = body["pages"][1]["thumb"]
    assert thumb.startswith("data:image/png;base64,")
    assert _png(thumb).shape[1] == 240


def test_pdf_pages_rejects_non_pdf(client, plan_bytes):
    r = client.post("/api/pdf/pages", files={"file": ("a.jpg", plan_bytes, "image/jpeg")})
    assert r.status_code == 400 and r.json()["error"]["code"] == "bad_request"
