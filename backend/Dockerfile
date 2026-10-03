FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/srv/backend

WORKDIR /srv/backend

# Install the runtime dependencies first so that this layer is cached across code changes.
COPY pyproject.toml ./
RUN python -c "import tomllib; print('\n'.join(tomllib.load(open('pyproject.toml', 'rb'))['project']['dependencies']))" > /tmp/requirements.txt \
    && pip install --no-cache-dir -r /tmp/requirements.txt \
    && rm /tmp/requirements.txt

COPY alembic.ini ./
COPY migrations ./migrations
COPY app ./app

RUN useradd --system --uid 10001 --no-create-home hiker
USER hiker

EXPOSE 8000

# Apply pending migrations of all modules, then start the API.
CMD ["sh", "-c", "alembic upgrade heads && exec uvicorn --factory app.main:create_app --host 0.0.0.0 --port 8000"]
