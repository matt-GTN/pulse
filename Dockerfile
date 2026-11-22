FROM python:3.12-slim

WORKDIR /app
ENV PYTHONPATH=/app \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

COPY --from=ghcr.io/astral-sh/uv:0.11.8 /uv /uvx /bin/

COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev

COPY . .

# Install cron + tzdata
RUN apt-get update && apt-get install -y cron tzdata && \
    rm -rf /var/lib/apt/lists/* && \
    ln -sf /usr/share/zoneinfo/Europe/Paris /etc/localtime && \
    echo "Europe/Paris" > /etc/timezone

# Set up cron job
COPY crontab /etc/cron.d/pulse
RUN chmod 0644 /etc/cron.d/pulse && crontab /etc/cron.d/pulse

# Create output directories
RUN mkdir -p /app/output/digests /app/data

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

CMD ["/entrypoint.sh"]
