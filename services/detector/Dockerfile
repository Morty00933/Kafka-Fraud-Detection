FROM python:3.11-slim

WORKDIR /app

# Если у тебя корпоративный прокси — можно пробросить ARG в build
ARG HTTP_PROXY
ARG HTTPS_PROXY
ARG NO_PROXY

ENV HTTP_PROXY=${HTTP_PROXY}
ENV HTTPS_PROXY=${HTTPS_PROXY}
ENV NO_PROXY=${NO_PROXY}

# Ставим только Python-зависимости (все бинарные колёса)
COPY services/detector/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --only-binary=:all: --prefer-binary -r /app/requirements.txt

# Код
COPY services/detector/ /app/

# Метрики поднимем отдельным HTTP-сервером внутри процесса
ENV PROMETHEUS_PORT=9000
ENV HOST=0.0.0.0
ENV PORT=8080

CMD ["python", "/app/app.py"]
