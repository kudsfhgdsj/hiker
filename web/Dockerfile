FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/srv/web

WORKDIR /srv/web

# Install the runtime dependencies first so that this layer is cached across code changes.
COPY pyproject.toml ./
RUN python -c "import tomllib; print('\n'.join(tomllib.load(open('pyproject.toml', 'rb'))['project']['dependencies']))" > /tmp/requirements.txt \
    && pip install --no-cache-dir -r /tmp/requirements.txt \
    && rm /tmp/requirements.txt

COPY hiker_web ./hiker_web

RUN useradd --system --uid 10002 --no-create-home hiker \
    && mkdir -p /data/sessions && chown -R hiker /data
USER hiker

ENV WEB_SESSION_DIR=/data/sessions
EXPOSE 8000

# The port is only published on 127.0.0.1, so the forwarded headers of the local reverse
# proxy can be trusted. No access log: the paths of public links contain their token.
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "2", "--threads", "4", "--timeout", "120", "--forwarded-allow-ips", "*", "--no-control-socket", "hiker_web.wsgi:app"]
