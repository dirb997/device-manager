FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY tests ./tests
COPY pytest.ini .

EXPOSE 8000

# Default to running the app, but can be overridden for testing
CMD ["sh", "-c", "python -m app.wait_for_db && uvicorn app.main:app --host 0.0.0.0 --port 8000"]