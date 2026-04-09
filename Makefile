.PHONY: infra-up infra-down infra-logs infra-clean infra-restart init-env status

COMPOSE_FILE = docker-compose.infra.yml

init-env:
	@if [ ! -f .env ]; then cp .env.example .env; echo ".env created, update passwords if needed"; else echo ".env already exists"; fi

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