# One image for both processes:
#   api    (default CMD) -> migrate + seed + uvicorn on :8000
#   worker (override)    -> arq app.worker.settings.WorkerSettings
ARG PYTHON_IMAGE=python:3.12-slim
FROM ${PYTHON_IMAGE}

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PYTHON=python3 \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /uvx /bin/

WORKDIR /app

# Dependencies first for layer caching.
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen --no-dev --no-install-project

COPY . .
RUN sed -i 's/\r$//' scripts/*.sh && chmod +x scripts/*.sh \
    && useradd --create-home --uid 10001 --shell /usr/sbin/nologin app \
    && mkdir -p /data/media \
    && chown -R app:app /app /data/media

USER app
EXPOSE 8000

CMD ["/app/scripts/start-api.sh"]
