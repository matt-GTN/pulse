FROM python:3.11-slim

WORKDIR /app
ENV PYTHONPATH=/app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

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

CMD ["sh", "-c", "printenv >> /etc/environment && cron -f"]
