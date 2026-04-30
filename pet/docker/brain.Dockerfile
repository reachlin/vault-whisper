FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends lynx && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY brain/ ./brain/
COPY config/ ./config/

CMD ["python", "-m", "brain.main"]
