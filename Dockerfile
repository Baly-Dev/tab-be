FROM python:3.11-slim-bookworm

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

COPY pyproject.toml /app/
COPY admin /app/admin/
COPY auth /app/auth/
COPY config /app/config/
COPY core /app/core/
COPY notifications /app/notifications/
COPY services /app/services/
COPY main.py db.py alembic.ini /app/
COPY alembic /app/alembic/

RUN pip install --upgrade pip \
    && pip install --no-cache-dir -e .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
