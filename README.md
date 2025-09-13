# Kafka Fraud Detection

Реализация системы онлайн-детекции подозрительных транзакций на базе **Kafka (Redpanda)**,  
**Python (FastAPI, aiokafka, scikit-learn)**, **Postgres**, **Redis** и **Prometheus**.

---

##  Возможности

- **Генерация транзакций** (producer) в Kafka (`transactions.v1`).
- **Онлайн-детектор** (detector):
  - подписка на Kafka,
  - проверка транзакций через **Isolation Forest** и эвристики,
  - сохранение алертов в Redis и Postgres,
  - отдача API (`/alerts`, `/health`).
- **Метрики Prometheus** на `:9000/metrics` (GC, latency, количество алертов).
- Поддержка дедупликации алертов в Redis (ключи `fraud:*`).

---

##  Архитектура проекта

```text
Kafka-Fraud-Detection/
│── docker-compose.yml         # оркестрация сервисов
│── .env                       # переменные окружения
│── services/
│   ├── producer/              # генератор транзакций
│   │   ├── main.py
│   │   ├── requirements.txt
│   │   └── Dockerfile
│   └── detector/              # сервис-детектор
│       ├── main.py
│       ├── model.py           # IsolationForest + эвристики
│       ├── api.py             # FastAPI (эндпоинты)
│       ├── requirements.txt
│       └── Dockerfile
│── migrations/
│   └── 001_init.sql           # схема Postgres (fraud_alerts)
````

---

##  Запуск

1. Клонируй репозиторий:

   ```bash
   git clone <repo_url>
   cd Kafka-Fraud-Detection
   ```

2. Создай файл `.env`:

   ```env
   POSTGRES_USER=app
   POSTGRES_PASSWORD=secret
   POSTGRES_DB=fraud
   ```

3. Подними все сервисы:

   ```bash
   docker compose up -d --build
   ```

4. Проверь состояние контейнеров:

   ```bash
   docker compose ps
   ```

---

## Проверка работы

### 1. Health-чек API

```bash
curl http://localhost:8080/health
# {"status":"ok"}
```

### 2. Последние алерты

```bash
curl "http://localhost:8080/alerts?limit=5"
```

Пример ответа:

```json
[
  {
    "tx_id": "tx_1539",
    "user_id": 4405,
    "amount": "1881.22",
    "location": "ES",
    "ts": "2025-09-13T07:46:41.314350Z",
    "score": -0.767,
    "reason": "iforest_score=-0.767; threshold=-0.657",
    "created_at": "2025-09-13T07:46:41.400Z"
  }
]
```

### 3. Ключи в Redis

```bash
docker compose exec redis redis-cli keys "fraud:*" | head -n 10
```

### 4. Счётчик алертов в Postgres

```bash
docker compose exec postgres \
  psql -U app -d fraud -c "SELECT count(*) FROM fraud_alerts;"
```

### 5. Метрики Prometheus

```bash
curl http://localhost:9000/metrics
```

---

## Используемые технологии

* **Python 3.11**: FastAPI, aiokafka, scikit-learn, psycopg2, redis-py
* **Kafka / Redpanda**: брокер сообщений
* **Postgres**: хранение истории алертов
* **Redis**: быстрый кеш и дедуп
* **Prometheus**: метрики мониторинга
* **Docker Compose**: оркестрация сервисов

---

## Дальнейшие улучшения

* Добавить обучение Isolation Forest на реальных данных (сейчас он обучен на рандомных фичах).
* Настроить Grafana для дашбордов.
* Добавить алертинг (Slack/Webhook при превышении лимита аномалий).
* Поддержка нескольких моделей (Rule-based + ML).

---

## Автор

Проект собран как учебный пример **real-time fraud detection pipeline** на Kafka.
