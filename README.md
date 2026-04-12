# PD Scanner

**PD Scanner** — распределённая система для автоматического обнаружения персональных данных (ПДн) в файлах различных форматов.

### Ключевые возможности

- Рекурсивное сканирование директорий с фильтрацией по расширению и размеру
- Дедупликация файлов через Redis (SHA-256 хэши)
- Асинхронная очередь задач через Kafka
- Распределённая обработка через Apache Spark
- Распознавание текста на изображениях через OCR-микросервис (Tesseract)
- 🇷🇺 Детекция ПДн РФ: паспорт, СНИЛС, ИНН, телефон, email (regex + эвристики)

## Требования

- **Python 3.11+**
- **Docker & Docker Compose v2+**
- **GNU Make**
- **Git**

## 🚀 Быстрый старт

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

## ⚙️ Конфигурация

Все параметры загружаются из `.env` через `pydantic-settings`. Отсутствие обязательных переменных приводит к ошибке валидации при старте.

### Локальный запуск vs Docker

| Запуск | Хосты в `.env` |
|--------|---------------|
| `make run` (на хосте) | `localhost` |
| В контейнере (будущее) | `postgres`, `redis`, `kafka`, `spark-master` |

### Разрешение конфликтов портов

Если порты `5432`, `6379`, `9092`, `8001` заняты:

1. Измените проброс в `docker-compose.infra.yml`:
   ```yaml
   ports:
     - "5433:5432"  # вместо 5432:5432
   ```
2. Обновите `.env`:
   ```env
   POSTGRES_PORT=5433
   ```
3. Перезапустите:
   ```bash
   make infra-clean && make infra-up
   ```

---

## 📦 Доступные команды

| Команда | Описание |
|---------|----------|
| `make infra-up` | Запуск инфраструктуры с ожиданием готовности |
| `make infra-down` | Остановка контейнеров (сохранение volumes) |
| `make infra-clean` | Полная очистка (контейнеры + volumes) |
| `make status` | Статус запущенных сервисов |
| `make install` | Создание venv + установка зависимостей |
| `make run` | Запуск основного приложения |
| `make ocr-up` | Запуск только OCR-сервиса |
| `make ocr-logs` | Логи OCR-сервиса |
| `make lint` | Статический анализ (Ruff) |
| `make format` | Автоформатирование кода |
| `make check` | Полный контроль качества (Lint + Mypy) |

---

## ✅ Проверка работоспособности

После `make run` ожидайте в логах:

```text
[info] Start APP app_name=pd-scanner env=dev
[info] Connection to PostgreSQL established version=PostgreSQL 15.x...
[info] Connection to Redis established
[info] Kafka producer initialized bootstrap=localhost:9092
[info] SparkSession init master=local[2]
[info] Starting Spark Processing Job files_count=77
[info] Processing batch 1/26 batch_size=3
[warning] PD Detected! path=.../doc.txt categories={'passport': 1, 'snils': 1}
[info] Spark Job Finished stats={'success': 75, 'parse_error': 1, 'pd_found': 18}
```

### Ручная проверка соединений

```bash
# PostgreSQL
docker exec pd_postgres psql -U scanner -d pd_scanner -c "SELECT 1;"

# Redis
docker exec pd_redis redis-cli -a "$(grep REDIS_PASSWORD .env | cut -d= -f2)" ping
# Ожидаем: PONG

# Kafka
docker exec pd_kafka /opt/kafka/bin/kafka-topics.sh \
  --bootstrap-server localhost:9092 --list

# Spark UI
# Откройте в браузере: http://localhost:8080

# OCR Service Health
curl http://localhost:8001/health
# Ожидаем: {"status":"healthy","tesseract_version":"5.3.0",...}
```