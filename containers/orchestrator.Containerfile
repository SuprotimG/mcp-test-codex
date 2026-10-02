FROM python:3.12-slim

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md /app/
COPY src /app/src
COPY docs /app/docs

RUN pip install --no-cache-dir .

CMD ["uvicorn", "software_factory.api.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8080"]

