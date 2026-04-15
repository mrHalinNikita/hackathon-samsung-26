.PHONY: infra-up infra-down infra-logs infra-clean infra-restart status \
        venv install run lint format check

COMPOSE_FILE = docker-compose.infra.yml

# INFRASTRUCTURE

# WINDOWS
# init-env:
#	@if not exist ".env" copy ".env.example" ".env" >nul

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
	curl -X POST http://localhost:$(OCR_PORT)/api/v1/ocr/extract \
	  -H "Content-Type: application/json" \
	  -d '{"file_path": "./test_dataset/scans/sample.jpg", "preprocess": true}'

# KUBERNETES (kind)

K8S_NAMESPACE = pd-scanner
K8S_MANIFESTS = deploy/k8s/base
KIND_CLUSTER = pd-scanner

k8s-generate:
	python deploy/k8s/scripts/generate-k8s-from-env.py --env-file .env.k8s

k8s-build:
	docker build -t pd-app:latest -f deploy/docker/app/Dockerfile .
	kind load docker-image pd-app:latest --name $(KIND_CLUSTER)

k8s-apply: k8s-generate
	kubectl apply -f $(K8S_MANIFESTS)/namespace.yaml
	kubectl apply -f $(K8S_MANIFESTS)/postgres/
	kubectl apply -f $(K8S_MANIFESTS)/redis/
	kubectl apply -f $(K8S_MANIFESTS)/kafka/
	kubectl apply -f $(K8S_MANIFESTS)/spark/
	kubectl apply -f $(K8S_MANIFESTS)/ocr/
	kubectl apply -f $(K8S_MANIFESTS)/app/

k8s-apply-app:
	kubectl apply -f $(K8S_MANIFESTS)/app/

k8s-clean:
	kubectl delete namespace $(K8S_NAMESPACE) --ignore-not-found
	kubectl create namespace $(K8S_NAMESPACE)

k8s-status:
	kubectl get pods -n $(K8S_NAMESPACE) -o wide

k8s-logs:
	kubectl logs -n $(K8S_NAMESPACE) -l app=pd-app -f

k8s-logs-pod:
	kubectl logs -n $(K8S_NAMESPACE) $(POD) -f

k8s-restart-app:
	kubectl rollout restart deployment pd-app -n $(K8S_NAMESPACE)

k8s-run-job:
	kubectl delete job pd-spark-scan-job -n $(K8S_NAMESPACE) --ignore-not-found
	kubectl apply -f $(K8S_MANIFESTS)/job/

k8s-job-logs:
	kubectl logs -n $(K8S_NAMESPACE) -l job-name=pd-spark-scan-job -f

k8s-jobs:
	kubectl get jobs -n $(K8S_NAMESPACE)

k8s-spark-ui:
	kubectl port-forward -n $(K8S_NAMESPACE) svc/pd-spark-master 8080:8080

k8s-ocr-api:
	kubectl port-forward -n $(K8S_NAMESPACE) svc/pd-ocr-service 8001:8000

k8s-postgres:
	kubectl port-forward -n $(K8S_NAMESPACE) pd-postgres-0 5432:5432

k8s-shell:
	kubectl exec -n $(K8S_NAMESPACE) -l app=pd-app -it -- /bin/bash

k8s-copy-data:
	docker exec $(KIND_CLUSTER)-control-plane mkdir -p /data/test_dataset
	docker cp ./test_dataset/. $(KIND_CLUSTER)-control-plane:/data/test_dataset/

k8s-deploy: k8s-build k8s-apply

k8s-redeploy: k8s-build k8s-apply-app k8s-restart-app

k8s-test-db:
	kubectl exec -n $(K8S_NAMESPACE) -l app=pd-app -- python -c \
	"import os,psycopg2;c=psycopg2.connect(host=os.environ['POSTGRES_HOST'],port=int(os.environ['POSTGRES_PORT']),database=os.environ['POSTGRES_DB'],user=os.environ['POSTGRES_USER'],password=os.environ['POSTGRES_PASSWORD']);print('Connected');c.close()"