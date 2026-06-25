FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    wget curl && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN pip install --no-cache-dir \
    fastapi==0.115.6 \
    uvicorn[standard]==0.34.0 \
    kokoro-onnx>=0.4.0 \
    onnxruntime>=1.17.0 \
    soundfile>=0.12.0 \
    numpy>=1.26.0

COPY server.py .
COPY entrypoint.sh .
RUN chmod +x entrypoint.sh

RUN mkdir -p /app/models

EXPOSE 8880

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8880"]
