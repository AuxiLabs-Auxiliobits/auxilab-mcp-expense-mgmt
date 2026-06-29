FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app

# Install deps first for layer caching.
COPY pyproject.toml ./
RUN pip install --no-cache-dir .

COPY app ./app
# Alembic config + migrations so the same image can run `alembic upgrade head`
# (used by the Container Apps "migrate" job before the app rolls out).
COPY alembic.ini ./alembic.ini
COPY alembic ./alembic

EXPOSE 8000
# Container Apps sets PORT; default to 8000 locally.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
