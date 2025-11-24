FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update && apt-get install -y \
    postgresql-client \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY pyproject.toml ./

RUN uv pip install --system --no-cache -r pyproject.toml

COPY . .

RUN mkdir -p /app/staticfiles /app/media

COPY docker-entrypoint.sh /app/docker-entrypoint.sh
RUN chmod +x /app/docker-entrypoint.sh

RUN useradd -m -u 1000 django && \
    chown -R django:django /app

USER django

EXPOSE 8000

ENTRYPOINT ["/app/docker-entrypoint.sh"]

CMD ["gunicorn", "tienda_calzados_marilo.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "4", "--timeout", "60"]
