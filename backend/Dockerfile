FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
# Build the chunk index at image build time.
RUN python -m app.ingest
EXPOSE 8000
# Set LLM_API_KEY, CORS_ORIGINS and TRUST_PROXY=1 as environment variables at run time.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
