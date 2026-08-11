FROM python:3.12-slim-bookworm

WORKDIR /app

COPY pyproject.toml ./
COPY src ./src
COPY alembic.ini ./
COPY migrations ./migrations

RUN python -m pip install --no-cache-dir .

CMD ["python", "-m", "uvicorn", "gateway.gateway_api.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
