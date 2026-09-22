FROM python:3.12-slim
WORKDIR /app
COPY server.py index.html ./
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
USER 1000:1000
CMD ["python", "server.py"]
