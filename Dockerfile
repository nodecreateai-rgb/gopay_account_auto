FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV GOPAY_API_PORT=28000

# 仅启动 API；注册由 GET /register 触发，不在启动时执行
EXPOSE 28000
CMD ["python", "api.py"]
