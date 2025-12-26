# builder
FROM python:3.9-slim AS builder

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# runner
FROM python:3.9-slim

WORKDIR /app

COPY --from=builder /install /usr/local

RUN apt-get update && apt-get install -y \
    libglib2.0-0 libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 \
    libcups2 libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 \
    libxrandr2 libgbm1 libasound2 \
    && rm -rf /var/lib/apt/lists/*

RUN playwright install chromium 
RUN playwright install-deps

COPY . .

CMD ["python", "-u", "main.py"]
