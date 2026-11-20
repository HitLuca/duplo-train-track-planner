FROM python:3.12-slim

WORKDIR /srv
COPY server.py ./
COPY backend ./backend
COPY app ./app

ENV PORT=8080 \
    DB_PATH=/data/trenino.db \
    PYTHONUNBUFFERED=1

VOLUME ["/data"]
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=3s CMD python -c "import urllib.request,sys; urllib.request.urlopen('http://localhost:8080/api/health'); sys.exit(0)"

CMD ["python", "server.py"]
