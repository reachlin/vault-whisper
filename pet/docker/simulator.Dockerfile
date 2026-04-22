FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY simulator/ ./simulator/

EXPOSE 18080

CMD ["uvicorn", "simulator.server:app", "--host", "0.0.0.0", "--port", "18080"]
