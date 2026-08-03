FROM python:3.12-slim

WORKDIR /app
RUN pip install --no-cache-dir "fastapi>=0.115" "uvicorn[standard]>=0.32" "python-multipart>=0.0.17"

COPY stub.py .

EXPOSE 8900
CMD ["uvicorn", "stub:app", "--host", "0.0.0.0", "--port", "8900"]
