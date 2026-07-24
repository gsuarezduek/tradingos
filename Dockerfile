FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml ./
COPY src ./src
COPY data/historical/BTCUSDT_1h.parquet ./data/historical/BTCUSDT_1h.parquet

RUN pip install --no-cache-dir .

ENV TRADINGOS_DATA_DIR=/app/data/historical

EXPOSE 8080

CMD ["uvicorn", "tradingos.api.main:app", "--host", "0.0.0.0", "--port", "8080"]
