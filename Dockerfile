FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml ./
COPY alembic.ini ./
COPY alembic ./alembic
COPY src ./src
COPY scripts ./scripts
COPY data/historical ./data/historical

RUN pip install --no-cache-dir .

ENV TRADINGOS_DATA_DIR=/app/data/historical
ENV TRADINGOS_ALEMBIC_INI=/app/alembic.ini

EXPOSE 8080

CMD ["uvicorn", "tradingos.api.main:app", "--host", "0.0.0.0", "--port", "8080"]
