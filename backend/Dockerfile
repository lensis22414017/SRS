FROM python:3.11-slim
WORKDIR /app/backend
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
# weasyprint PDF 渲染所需的系统库 (Pango/Cairo/GDK) + 中文字体(matplotlib 报告图件)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf-2.0-0 \
    libffi-dev libcairo2 libgobject-2.0-0 shared-mime-info \
    fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*
COPY backend/requirements.txt .
RUN pip install --default-timeout=300 --retries 10 --no-cache-dir -r requirements.txt
COPY backend/ .
COPY data /app/data
COPY ml /app/ml
COPY reporting /app/reporting
COPY scripts /app/scripts
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
