FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt requirements-test.txt ./
RUN pip install --no-cache-dir -r requirements.txt -r requirements-test.txt

COPY simulator/ ./simulator/
COPY brain/ ./brain/
COPY mcp_server/ ./mcp_server/
COPY pytest.ini .

CMD ["pytest", "-v", "--tb=short"]
