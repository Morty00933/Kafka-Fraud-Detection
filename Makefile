# =============================================================================
#   Kafka Fraud Detection - Makefile
# =============================================================================

.PHONY: help up down build logs status restart clean health

SHELL := C:/PROGRA~1/Git/usr/bin/bash.exe

.DEFAULT_GOAL := help

help:
	@echo ""
	@echo "  Kafka Fraud Detection"
	@echo ""
	@echo "  make up       - Start all services"
	@echo "  make down     - Stop all"
	@echo "  make build    - Build images"
	@echo "  make logs     - Logs for all services"
	@echo "  make status   - Container status"
	@echo "  make health   - Health check"
	@echo "  make clean    - Remove containers + volumes"
	@echo ""
	@echo "  Ports:"
	@echo "    Detector:  http://localhost:8080"
	@echo "    API:       http://localhost:8081"
	@echo "    Redpanda:  localhost:9092 (Kafka)"
	@echo "    Postgres:  localhost:5432"
	@echo "    Redis:     localhost:6379"
	@echo ""

up: build
	@echo "Starting Kafka Fraud Detection..."
	docker compose up -d
	@echo ""
	@echo "Services started!"
	@echo "  Detector:  http://localhost:8080"
	@echo "  API:       http://localhost:8081"
	@echo ""

down:
	docker compose down

build:
	docker compose build

rebuild:
	docker compose build --no-cache

logs:
	docker compose logs -f

logs-detector:
	docker compose logs -f detector

logs-api:
	docker compose logs -f api

logs-producer:
	docker compose logs -f producer

status:
	docker compose ps

restart:
	docker compose restart

health:
	@echo ""
	@echo "Health check..."
	@echo -n "  Detector (8080):  " && curl -sf http://localhost:8080/health >/dev/null 2>&1 && echo "OK" || echo "FAIL"
	@echo -n "  API (8081):       " && curl -sf http://localhost:8081/health >/dev/null 2>&1 && echo "OK" || echo "FAIL"
	@echo -n "  Redpanda (9644):  " && curl -sf http://localhost:9644/v1/status/ready >/dev/null 2>&1 && echo "OK" || echo "FAIL"
	@echo -n "  Redis:            " && docker compose exec -T redis redis-cli ping 2>/dev/null | grep -q PONG && echo "OK" || echo "FAIL"
	@echo -n "  Postgres:         " && docker compose exec -T postgres pg_isready -U app -d fraud 2>/dev/null | grep -q "accepting" && echo "OK" || echo "FAIL"
	@echo ""

shell-detector:
	docker compose exec detector bash

shell-api:
	docker compose exec api bash

db-shell:
	docker compose exec postgres psql -U app -d fraud

redis-cli:
	docker compose exec redis redis-cli

clean:
	docker compose down -v --remove-orphans
	@echo "Containers and volumes removed."

clean-all:
	docker compose down -v --remove-orphans --rmi all
	@echo "Everything removed."
