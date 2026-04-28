# Build context: repo root (set in docker-compose.yml)
FROM python:3.11-slim

RUN pip install uv

WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY api/ api/
COPY pw/ pw/
# Non-editable install — more reliable in Docker than hatchling's editable import hooks
RUN uv pip install --system api/ pw/

# Chromium + all its system deps in one shot
RUN playwright install chromium --with-deps

# WeasyPrint + virtual display deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpangocairo-1.0-0 libgdk-pixbuf-xlib-2.0-0 shared-mime-info \
    xvfb x11vnc novnc \
    && rm -rf /var/lib/apt/lists/*

ENV APP_ROOT=/app
ENV DISPLAY=:99
# Explicit module search paths — no reliance on editable install hooks
ENV PYTHONPATH=/app/api:/app

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8000 6080
CMD ["/entrypoint.sh"]
