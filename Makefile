.PHONY: infra-up infra-down infra-logs infra-clean infra-restart status \
        venv install run lint format check

COMPOSE_FILE = docker-compose.infra.yml

# INFRASTRUCTURE

init-env:
	@if [ ! -f .env ]; then cp .env.example .env; fi

infra-up: init-env
	docker compose -f $(COMPOSE_FILE) up -d --wait

infra-down:
	docker compose -f $(COMPOSE_FILE) down

infra-restart:
	docker compose -f $(COMPOSE_FILE) up -d --force-recreate

infra-logs:
	docker compose -f $(COMPOSE_FILE) logs -f

infra-clean:
	docker compose -f $(COMPOSE_FILE) down -v
	docker volume prune -f

status:
	docker compose -f $(COMPOSE_FILE) ps

# PYTHON ENV

venv:
	python3.11 -m venv .venv

install: venv
	.venv/bin/pip install --upgrade pip
	.venv/bin/pip install -r requirements.txt
	.venv/bin/pip install -r requirements-ocr.txt

# RUN

run:
	.venv/bin/python src/main.py

# CODE QUALITY

lint:
	.venv/bin/ruff check src/

format:
	.venv/bin/ruff format src/

check: lint
	.venv/bin/mypy src/

# OCR SERVICE

ocr-up:
	docker compose -f docker-compose.infra.yml up -d ocr-service ocr-worker

ocr-down:
	docker compose -f docker-compose.infra.yml down ocr-service ocr-worker

ocr-logs:
	docker compose -f docker-compose.infra.yml logs -f ocr-service ocr-worker

ocr-test:
	curl -X POST http://localhost:$(OCR_SERVICE_PORT)/api/v1/ocr/extract \
	  -H "Content-Type: application/json" \
	  -d '{"file_path": "./test_dataset/scans/sample.jpg", "preprocess": true}'