# RescueNet AI backend (docs/07 T-05, T-21 — single deployable)
# Referenced by deploy/docker-compose.yml, service `backend`, profile `app`.
FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml ./
COPY src ./src

RUN pip install --no-cache-dir .

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

EXPOSE 8000

CMD ["uvicorn", "rescuenet.app:app", "--host", "0.0.0.0", "--port", "8000"]
