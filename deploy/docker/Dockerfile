# StankBot — container image.
# Non-root, uv-based install, SQLite data lives in /data (bind-mount a host dir).

FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN useradd --create-home --uid 10001 stankbot

# su-exec drops privileges from the root entrypoint to the stankbot user
# after we've fixed ownership on the (root-owned) Railway volume mount.
RUN apt-get update && apt-get install -y --no-install-recommends gosu \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
COPY migrations ./migrations
COPY alembic.ini ./
COPY deploy/docker/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

RUN pip install --upgrade pip && pip install .

RUN install -d -o stankbot -g stankbot /data

ENV DATABASE_URL=sqlite+aiosqlite:////data/stankbot.db \
    TEMPLATES_DIR=/data/templates

EXPOSE 8000

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["python", "-m", "stankbot"]
