FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN apt-get update \
    && apt-get install -y --no-install-recommends default-mysql-client rclone \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir -r /app/requirements.txt

COPY . /app

RUN addgroup --system app \
    && adduser --system --ingroup app app \
    && mkdir -p /app/logs /app/uploads /app/db_backups /app/monthly_backups /app/distribution_manifests \
    && chown -R app:app /app

EXPOSE 8080

USER app

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
