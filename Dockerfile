FROM python:3.11-slim


LABEL maintainer="Luiz Ardezzoni <luiz@exemplo.com>"
LABEL description="TCC - Backtesting reprodutível em Python com Backtrader"


ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    git build-essential \
    && rm -rf /var/lib/apt/lists/*


WORKDIR /app


COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt


COPY src/ ./src/
COPY data/ ./data/


RUN find ./src ./data -type f -exec sha256sum {} \; > build_hashes.txt


CMD ["python", "src/run_backtests.py"]
