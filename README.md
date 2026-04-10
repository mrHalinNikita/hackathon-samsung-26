# Инфраструктура и запуск

Документ описывает процесс инициализации инфраструктуры и запуска базового каркаса приложения на текущем этапе разработки.

## Требования

- Python 3.11+
- Docker & Docker Compose v2+
- GNU Make
- Git

## Быстрый старт

1. **Инициализация конфигурации**
   ```bash
   # При необходимости отредактируйте порты в .env
   cp .env.example .env
   ```

2. **Запуск инфраструктуры**
   ```bash
   make infra-up
   ```
   Команда создаёт сеть, volumes и поднимает PostgreSQL, Redis, Kafka. Процесс блокируется до прохождения всех healthcheck-проверок.

3. **Подготовка Python-окружения**
   ```bash
   make install
   ```
   Создаёт директорию `.venv/`, обновляет pip и устанавливает зависимости из `requirements.txt`.

4. **Запуск приложения**
   ```bash
   make run
   ```
   Приложение валидирует конфигурацию, устанавливает соединения с инфраструктурой и переходит в режим ожидания команд.

## Конфигурация

Все параметры загружаются из файла `.env` через `pydantic-settings`. 

### Локальный запуск vs Docker
При запуске через `make run` приложение выполняется на хост-машине, поэтому в `.env` необходимо указывать `localhost`:
```env
POSTGRES_HOST=localhost
REDIS_HOST=localhost
KAFKA_BROKER=localhost
```
> **Примечание:** При запуске приложения внутри Docker-контейнера (на следующих этапах) значения хостов необходимо будет заменить на имена сервисов (`postgres`, `redis`, `kafka`).

### Разрешение конфликтов портов
Если порты `5432`, `6379` или `9092` уже используются другими процессами на хосте:
1. Измените проброс портов в `docker-compose.infra.yml` (например, `5433:5432`).
2. Обновите соответствующие переменные в `.env` (`POSTGRES_PORT=5433`).
3. Перезапустите инфраструктуру: `make infra-clean && make infra-up`.


## Доступные команды

| Команда | Описание |
|---------|----------|
| `make infra-up` | Запуск инфраструктуры с ожиданием готовности |
| `make infra-down` | Остановка контейнеров (сохранение volumes) |
| `make infra-clean` | Полная очистка (контейнеры + volumes) |
| `make status` | Вывод состояния запущенных сервисов |
| `make install` | Создание venv и установка зависимостей |
| `make run` | Запуск основного приложения |
| `make lint` | Статический анализ кода (Ruff) |
| `make format` | Автоформатирование кода |
| `make check` | Полный контроль качества (Lint + Mypy) |

## Проверка работоспособности

После выполнения `make run` в консоли должны отобразиться записи об успешной инициализации:

```text
[info] Start APP app_name=pd-scanner env=dev log_level=INFO
[info] Connection to PostgreSQL established version=PostgreSQL 15.x...
[info] Connection to Redis established
[info] Kafka producer initialized bootstrap=localhost:9092
[info] The application is ready to work! message='Waiting for tasks...'
```

Для ручной проверки соединений:
```bash
# PostgreSQL
docker exec pd_postgres psql -U scanner -d pd_scanner -c "SELECT 1;"

# Redis
docker exec pd_redis redis-cli -a "$(grep REDIS_PASSWORD .env | cut -d= -f2)" ping

# Kafka
docker exec pd_kafka kafka-topics.sh --bootstrap-server localhost:9092 --list
```