FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN pip install --no-cache-dir \
    fastapi==0.115.6 \
    uvicorn[standard]==0.34.0 \
    requests \
    numpy

COPY server.py .

EXPOSE 8899

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8899"]
