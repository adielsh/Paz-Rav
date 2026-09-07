# Python 3.12 pinned for ecosystem stability (SQLAlchemy/psycopg/pandas_market_calendars).
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    TZ=America/New_York

WORKDIR /srv

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

# Persistent daemon; orders gated by PLACE_ORDERS env (default dry-run).
CMD ["python", "-m", "app.main"]
