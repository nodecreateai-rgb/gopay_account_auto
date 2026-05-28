FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV GOPAY_API_PORT=28000

# Dokploy 默认 python main.py → 仅启动 API，不自动注册
EXPOSE 28000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:28000/health')" || exit 1
CMD ["python", "main.py"]
