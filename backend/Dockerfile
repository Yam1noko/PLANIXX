FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/opt \
    PORT=8000 \
    RUN_MIGRATIONS=true

WORKDIR /opt/backend

RUN apt-get update \
    && apt-get install -y --no-install-recommends bash \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /tmp/requirements.txt

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r /tmp/requirements.txt

COPY . /opt/backend

RUN mkdir -p /opt/backend/data/user_profiles /opt/backend/data/scorer_chunks \
    && chmod +x /opt/backend/docker-entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/opt/backend/docker-entrypoint.sh"]
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
