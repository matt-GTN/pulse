#!/bin/sh
# Export only the required vars so cron jobs can access them.
# /etc/environment is read by the Debian cron daemon before each job.
for var in \
    DATABASE_URL \
    TELEGRAM_BOT_TOKEN \
    TELEGRAM_CHAT_ID \
    DIGEST_BASE_URL \
    LLM_PROVIDER \
    GEMINI_API_KEY \
    GEMINI_MODEL \
    GROQ_API_KEY \
    TZ \
    LOG_LEVEL \
    PYTHONPATH; do
    val=$(printenv "$var")
    [ -n "$val" ] && echo "$var=$val" >> /etc/environment
done

exec cron -f
