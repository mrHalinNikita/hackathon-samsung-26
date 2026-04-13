# PD Scanner

**PD Scanner** — распределённая система для автоматического обнаружения персональных данных (ПДн) в файлах различных форматов с поддержкой локального запуска (Docker Compose) и развёртывания в Kubernetes.


### Ключевые возможности

- 🔍 Рекурсивное сканирование директорий с фильтрацией по расширению и размеру
- 🔐 Дедупликация файлов через Redis (SHA-256 хэши)
- 📡 Асинхронная очередь задач через Kafka
- ⚡ Распределённая обработка через Apache Spark (локально или в Kubernetes)
- 🔤 Распознавание текста на изображениях через OCR-микросервис (Tesseract)
- 🇷🇺 Детекция ПДн РФ: паспорт, СНИЛС, ИНН, телефон, email (regex + эвристики + NLP)

## Требования

### Базовые (для всех режимов)

| Компонент | Версия | Установка |
|-----------|--------|-----------|
| **Python** | 3.11+ | `pyenv install 3.11 && pyenv local 3.11` |
| **Docker** | 24+ | [docker.com](https://docs.docker.com/get-docker/) |
| **Docker Compose** | v2+ | Входит в Docker Desktop / `apt install docker-compose-plugin` |
| **GNU Make** | 4.0+ | `apt install make` / `brew install make` |
| **Git** | 2.30+ | `apt install git` / `brew install git` |

### Дополнительно для Kubernetes

| Компонент | Версия | Установка |
|-----------|--------|-----------|
| **kind** | 0.20+ | [kind.sigs.k8s.io](https://kind.sigs.k8s.io/docs/user/quick-start/#installation) |
| **kubectl** | 1.28+ | [kubernetes.io](https://kubernetes.io/docs/tasks/tools/) |
| **ОЗУ** | 8+ ГБ | Рекомендуется 16 ГБ для комфортной работы |
| **Диск** | ~10 ГБ | Для образов + тестовый датасет |

## 🐳 Локальный запуск (Docker Compose)

### 1. Инициализация конфигурации
```bash
# Скопировать шаблон .env и при необходимости отредактировать порты
cp .env.example .env
```

### 2. Запуск инфраструктуры
```bash
make infra-up
```
Команда поднимает в Docker:
- PostgreSQL 15 (БД)
- Redis 7 (кэш/дедупликация)
- Kafka 3.7 (очередь сообщений)
- Spark 3.5 (распределённая обработка)
- OCR-Service (распознавание текста на изображениях)

> ⏱ Первый запуск может занять 2–5 минут (скачивание образов).

### 3. Подготовка Python-окружения
```bash
make install
```
Создаёт `.venv/`, обновляет pip и устанавливает зависимости.

### 4. Запуск приложения
```bash
make run
```
Приложение:
1. Валидирует конфигурацию из `.env`
2. Подключается к инфраструктуре
3. Сканирует `SCAN_ROOT_PATH` (по умолчанию `./test_dataset`)
4. Отправляет задачи в Kafka / Spark
5. Выводит результаты детекции ПДн в логи

> 💡 Для повторного сканирования тех же файлов очистите Redis:
> ```bash
> docker exec -it pd_redis redis-cli -a "$(grep REDIS_PASSWORD .env | cut -d= -f2)" FLUSHDB
> ```

---

## ☸️ Развёртывание в Kubernetes

### 📦 Шаг 0: Установка зависимостей

```bash
# 1. Установите kind (Kubernetes in Docker)
# macOS:
brew install kind
# Linux:
curl -Lo ./kind https://kind.sigs.k8s.io/dl/v0.20.0/kind-linux-amd64
chmod +x ./kind && sudo mv ./kind /usr/local/bin/kind

# 2. Установите kubectl
# macOS:
brew install kubectl
# Linux:
curl -LO "https://dl.k8s.io/release/$(curl -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
chmod +x kubectl && sudo mv kubectl /usr/local/bin/

# 3. Проверьте установку
kind version && kubectl version --client
```

### 🚀 Шаг 1: Создание кластера kind

```bash
# Создайте кластер с именем pd-scanner
kind create cluster --name pd-scanner

# Проверьте, что кластер работает
kubectl cluster-info --context kind-pd-scanner
# Ожидаем: Kubernetes control plane is running at https://127.0.0.1:XXXX
```

### 🔐 Шаг 2: Настройка конфигурации и секретов

```bash
# 1. Создайте файл конфигурации для Kubernetes
cp .env.k8s.example .env.k8s
# Отредактируйте .env.k8s, задав безопасные пароли

# 2. Сгенерируйте манифесты Kubernetes из .env.k8s
make k8s-generate

# 3. Проверьте, что секреты не попали в репозиторий
git status
# Убедитесь, что secret.yaml и .env.k8s в .gitignore
```

### 📦 Шаг 3: Сборка и загрузка образа

```bash
# Соберите образ приложения и загрузите его в кластер kind
make k8s-build

# Проверьте, что образ доступен в кластере
kind get nodes --name pd-scanner | xargs -I {} docker exec {} crictl images | grep pd-app
# Ожидаем: pd-app latest <image-id>
```

### 🗂️ Шаг 4: Подготовка данных

Так как kind запускает узлы внутри Docker-контейнеров, данные нужно скопировать внутрь:

```bash
# Скопируйте тестовый датасет в узел кластера
make k8s-copy-data

# Проверьте, что файлы на месте
docker exec pd-scanner-control-plane ls -la /data/test_dataset/ | head -5
```

### 🚀 Шаг 5: Развёртывание инфраструктуры

```bash
# Примените все манифесты (namespace, БД, очереди, Spark, OCR, приложение)
make k8s-apply

# Дождитесь готовности подов
make k8s-status
# Ожидаем: все поды в статусе Running или ContainerCreating
```

### ✅ Шаг 6: Проверка работоспособности

```bash
# 1. Проверьте логи приложения
make k8s-logs
# Ожидаем: [info] Connection to PostgreSQL established...

# 2. Проверьте подключение к БД из пода
make k8s-test-db
# Ожидаем: Connected

# 3. Откройте Spark UI в браузере (в отдельном терминале)
make k8s-spark-ui
# Перейдите по ссылке: http://localhost:8080
```

### 🔄 Шаг 7: Запуск распределённого сканирования

```bash
# Запустите Spark Job для сканирования датасета
make k8s-run-job

# Следите за прогрессом в реальном времени
make k8s-job-logs

# Проверьте статус выполнения
make k8s-jobs
# Ожидаем: pd-spark-scan-job  1/1  Completed
```

### ♻️ Быстрое обновление приложения после изменений в коде

```bash
# Пересобрать образ, загрузить в kind и перезапустить приложение
make k8s-redeploy

# Или по шагам:
make k8s-build
make k8s-apply-app
make k8s-restart-app
```

### 🧹 Очистка и сброс

```bash
# Удалить только приложение (инфраструктура останется)
kubectl delete deployment pd-app -n pd-scanner

# Полностью удалить namespace и создать заново
make k8s-clean

# Удалить весь кластер kind
kind delete cluster --name pd-scanner
```

## 🔧 Генерация секретов

```bash
# 1. Скопируйте шаблон
cp .env.k8s.example .env.k8s

# 2. Отредактируйте пароли
# Сгенерировать случайный пароль:
openssl rand -base64 32

# 3. Перегенерируйте манифесты
make k8s-generate

# 4. Примените изменения
kubectl apply -f deploy/k8s/base/app/
make k8s-restart-app
```

## 📦 Доступные команды

### 🔹 Инфраструктура (Docker Compose)

| Команда | Описание |
|---------|----------|
| `make infra-up` | Запуск инфраструктуры с ожиданием готовности |
| `make infra-down` | Остановка контейнеров (сохранение volumes) |
| `make infra-clean` | Полная очистка (контейнеры + volumes) |
| `make status` | Статус запущенных сервисов |
| `make ocr-up` | Запуск только OCR-сервиса |
| `make ocr-logs` | Логи OCR-сервиса |

### 🔹 Разработка (Python)

| Команда | Описание |
|---------|----------|
| `make install` | Создание venv + установка зависимостей |
| `make run` | Запуск основного приложения |
| `make lint` | Статический анализ (Ruff) |
| `make format` | Автоформатирование кода |
| `make check` | Полный контроль качества (Lint + Mypy) |

### 🔹 Kubernetes

| Команда | Описание |
|---------|----------|
| `make k8s-generate` | Генерация манифестов из `.env.k8s` |
| `make k8s-build` | Сборка образа и загрузка в kind |
| `make k8s-apply` | Применение всех манифестов |
| `make k8s-apply-app` | Применение только манифестов приложения |
| `make k8s-clean` | Удаление namespace и создание заново |
| `make k8s-status` | Список всех подов с деталями |
| `make k8s-logs` | Логи основного приложения в реальном времени |
| `make k8s-restart-app` | Перезапуск deployment приложения |
| `make k8s-run-job` | Запуск Spark Scan Job |
| `make k8s-job-logs` | Логи Spark Job в реальном времени |
| `make k8s-jobs` | Статус всех задач (Jobs) |
| `make k8s-spark-ui` | Проброс порта для Spark UI (localhost:8080) |
| `make k8s-ocr-api` | Проброс порта для OCR API (localhost:8001) |
| `make k8s-postgres` | Проброс порта для локального доступа к PostgreSQL |
| `make k8s-shell` | Интерактивная консоль внутри пода приложения |
| `make k8s-copy-data` | Копирование `./test_dataset` в узел kind |
| `make k8s-deploy` | Полный цикл: сборка → загрузка → деплой |
| `make k8s-redeploy` | Быстрый деплой приложения после изменений в коде |
| `make k8s-test-db` | Проверка подключения к БД из пода |

---

### 🔍 Полезные команды для отладки

```bash
# Детальная информация о поде
kubectl describe pod -n pd-scanner <pod-name>

# Логи предыдущего экземпляра пода (после краша)
kubectl logs -n pd-scanner -l app=pd-app --previous

# Интерактивная консоль в поде
make k8s-shell

# Проверка переменных окружения в поде
kubectl exec -n pd-scanner -l app=pd-app -- env | grep POSTGRES

# Мониторинг ресурсов в реальном времени
kubectl top pods -n pd-scanner

# Проверка событий в namespace
kubectl get events -n pd-scanner --sort-by='.lastTimestamp'
```

### 🧪 Тестирование

```bash
# Запуск линтера и форматирования
make lint && make format

# Запуск статического анализа типов
make check

# Локальный запуск с тестовым датасетом
make run

# Проверка в Kubernetes
make k8s-deploy && make k8s-run-job && make k8s-job-logs
```