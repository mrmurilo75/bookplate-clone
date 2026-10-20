FROM python:3.13-slim
RUN pip install --no-cache-dir "uv>=0.11,<0.12"
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PROJECT_ENVIRONMENT=/app/.venv PATH="/app/.venv/bin:$PATH"
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project
COPY . .
RUN uv sync --frozen --no-dev
ENV UPLOADS_DIR=/data/uploads
EXPOSE 8000
# Migrations run automatically on start.
CMD ["uvicorn", "bookplate.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
