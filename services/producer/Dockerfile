FROM python:3.11-slim

WORKDIR /app

ARG HTTP_PROXY
ARG HTTPS_PROXY
ARG NO_PROXY
ENV HTTP_PROXY=${HTTP_PROXY}
ENV HTTPS_PROXY=${HTTPS_PROXY}
ENV NO_PROXY=${NO_PROXY}

COPY services/producer/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --only-binary=:all: --prefer-binary -r /app/requirements.txt

COPY services/producer/ /app/

ENV KAFKA_BOOTSTRAP=redpanda:9092
ENV TOPIC_TRANSACTIONS=transactions.v1
ENV RATE_PER_SEC=50

CMD ["python", "/app/app.py"]
