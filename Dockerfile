FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV GOPAY_API_PORT=28000
ENV PORT=28000

# Dokploy: Domains 或 Advanced→Ports 需指向容器端口 28000
EXPOSE 28000
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD python -c "import os,urllib.request; p=os.environ.get('PORT') or os.environ.get('GOPAY_API_PORT') or '28000'; urllib.request.urlopen(f'http://127.0.0.1:{p}/health')" || exit 1
CMD ["python", "main.py"]
