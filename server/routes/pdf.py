"""/api/pdf: page thumbnails of a PDF before a project is created (stateless, nothing is stored)."""

import base64
from typing import Annotated

from fastapi import APIRouter, File, Request, UploadFile

from core.extraction.preprocess import pdf_thumbnails
from server.errors import ApiError
from server.routes.projects import CHUNK, _read_limited

router = APIRouter(prefix="/api/pdf")


@router.post("/pages")
async def pages(request: Request, file: Annotated[UploadFile, File()]):
    data = await _read_limited(file, request.app.state.settings.max_upload_mb * CHUNK)
    try:
        thumbs = pdf_thumbnails(data)
    except ValueError as e:
        raise ApiError(400, "bad_request", str(e)) from None
    return {"page_count": len(thumbs),
            "pages": [{"page": i + 1, "thumb": "data:image/png;base64," + base64.b64encode(t).decode()}
                      for i, t in enumerate(thumbs)]}
