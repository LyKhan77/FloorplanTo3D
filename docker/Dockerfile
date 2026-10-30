# syntax=docker/dockerfile:1
# One image: FastAPI + pipeline + Blender (CPU, headless) + the built dashboard. Context = repo root:
#   docker compose -f docker/compose.yaml up -d --build

FROM node:24-bookworm-slim AS web
WORKDIR /src/web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
COPY benchmarks/gatsu/gt_spec.json /src/benchmarks/gatsu/
RUN npm run build

FROM ubuntu:24.04
ARG BLENDER_VERSION=5.2.2
ENV DEBIAN_FRONTEND=noninteractive
# Blender headless needs X11 client libs and Mesa (llvmpipe) for the Workbench render; Pango for WeasyPrint;
# Plex for the PDF report
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates curl xz-utils \
        libx11-6 libxi6 libxxf86vm1 libxfixes3 libxrender1 libxkbcommon0 libsm6 libice6 \
        libegl1 libgl1 libgl1-mesa-dri libglx-mesa0 \
        libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz0b fonts-ibm-plex \
        libglib2.0-0 libgomp1 \
    && rm -rf /var/lib/apt/lists/*
RUN curl -fsSL "https://download.blender.org/release/Blender${BLENDER_VERSION%.*}/blender-${BLENDER_VERSION}-linux-x64.tar.xz" \
        | tar -xJ -C /opt \
    && ln -s "/opt/blender-${BLENDER_VERSION}-linux-x64" /opt/blender

COPY --from=ghcr.io/astral-sh/uv:0.11.3 /uv /usr/local/bin/uv
ENV UV_PYTHON_INSTALL_DIR=/opt/python UV_LINK_MODE=copy UV_COMPILE_BYTECODE=1
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --python 3.12
COPY core core
COPY server server
COPY builder builder
COPY schema schema
COPY --from=web /src/web/dist web/dist

ENV PATH=/app/.venv/bin:$PATH DATA_DIR=/data BLENDER_BIN=/opt/blender/blender BLENDER_RENDER_DEVICE=CPU
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
    CMD curl -fsS http://localhost:8000/api/health || exit 1
CMD ["uvicorn", "server.app:app", "--host", "0.0.0.0", "--port", "8000"]
