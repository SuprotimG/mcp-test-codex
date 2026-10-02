FROM python:3.12-slim

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends git nodejs npm ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md /app/
COPY src /app/src
COPY docs /app/docs

RUN pip install --no-cache-dir .

CMD ["python", "-m", "software_factory.cli", "run-worker"]

