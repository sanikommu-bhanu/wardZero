# API image. NOT BUILT in the authoring sandbox (no Docker, no network) - first build happens on your machine.
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY apps/__init__.py apps/__init__.py
COPY apps/api apps/api
COPY apps/simulator apps/simulator
COPY database database
COPY ml ml
COPY services services
RUN useradd -r -u 10001 wz && mkdir -p /app/data && chown -R wz /app/data
USER wz
VOLUME ["/app/data"]
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s CMD python -c "import urllib.request as u; u.urlopen('http://127.0.0.1:8000/health', timeout=2)"
CMD ["uvicorn", "apps.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
