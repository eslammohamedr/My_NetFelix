FROM python:3.12-slim
WORKDIR /app
COPY server.py catalog.py sources.py index.html search.html manifest.json sw.js ./
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
USER 1000:1000
CMD ["python", "server.py"]
