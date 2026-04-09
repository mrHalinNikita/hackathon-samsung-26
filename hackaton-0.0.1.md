# План реализации системы обнаружения и классификации персональных данных (PD Scanner)


- рекурсивный сканер файловой системы с поддержкой множества форматов;
- микросервис OCR для обработки изображений и сканов;
- парсеры документов (PDF, DOCX, XLSX, HTML, CSV, JSON);
- распределённую обработку через Apache Spark (PySpark);
- асинхронную коммуникацию через брокер сообщений (Kafka/RabbitMQ);
- ML-модуль для классификации типов ПДн (УЗ-1 - УЗ-4);
- оркестрацию пайплайнов через Apache Airflow;
- контейнеризацию всех компонентов через Docker;
- хранение результатов в PostgreSQL;
- мониторинг, логирование и health-checks.

---

## Целевой результат

На выходе должен получиться рабочий каркас распределённой системы со следующими возможностями:

- запуск всех сервисов через `docker-compose up`;
- конфигурация через `.env` и централизованный config loader;
- рекурсивное сканирование директорий с фильтрацией по расширениям;
- извлечение текста из 10+ форматов файлов;
- детекция ПДн через комбинированный подход: regex + NLP + ML;
- классификация по уровням защиты (УЗ-1 - УЗ-4) согласно 152-ФЗ;
- генерация отчётов в форматах: JSON, CSV, Markdown, HTML;
- горизонтальное масштабирование через Spark workers;
- API для управления сканированием и получения результатов (FastAPI);
- интеграция с Airflow для планирования и мониторинга задач.

---

## Архитектурный подход

```
┌─────────────────────────────────────────────────────────┐
│                    Apache Airflow                       │
│              (оркестрация ETL-пайплайнов)               │
└─────────────────────────┬───────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────┐
│                 File Scanner Service                    │
│        (рекурсивный обход, фильтрация, enqueue)         │
└─────────────────────────┬───────────────────────────────┘
                          │
                   ┌──────▼──────┐
                   │   Message   │
                   │   Broker    │
                   │ (Kafka/RMQ) │
                   └──────┬──────┘
                          │
     ┌────────────────────┼────────────────────┐
     │                    │                    │
┌────▼────┐      ┌───────▼───────┐    ┌───────▼───────┐
│  OCR    │      │ Document      │    │ Structured    │
│ Service │      │ Parser        │    │ Data Parser   │
│FastAPI+ │      │ Service       │    │ Service       │
│ Celery  │      │ (PDF/DOCX)    │    │ (XLSX/CSV)    │
└────┬────┘      └───────┬───────┘    └───────┬───────┘
     │                   │                    │
     └───────────────────┼────────────────────┘
                         │
                  ┌──────▼──────┐
                  │   Apache    │
                  │    Spark    │
                  │  (PySpark   │
                  │   + MLlib)  │
                  └──────┬──────┘
                         │
                  ┌──────▼──────┐
                  │   Results   │
                  │   Storage   │
                  │ PostgreSQL  │
                  │   + MinIO   │
                  └──────┬──────┘
                         │
                  ┌──────▼──────┐
                  │   Reporting │
                  │   API       │
                  │  (FastAPI)  │
                  └─────────────┘
```

---

## 4. Технологический стек

| Компонент | Технология | Обоснование |
|-----------|-----------|-------------|
| **Язык** | Python 3.10+ | Экосистема для NLP, OCR, ML; быстрая разработка |
| **OCR** | Tesseract OCR + pytesseract + OpenCV | Поддержка русского языка, предобработка изображений |
| **Парсинг документов** | pdfplumber, python-docx, openpyxl, BeautifulSoup | Надёжные библиотеки для извлечения текста |
| **NLP (RU)** | Natasha, pymorphy2, spaCy (ru_core_news) | Распознавание ФИО, адресов, организаций |
| **ML-классификация** | scikit-learn / Spark MLlib / DeepPavlov | Гибкость: от rule-based до трансформеров |
| **Распределённая обработка** | Apache Spark (PySpark) | Масштабирование на большие объёмы данных |
| **Брокер сообщений** | Apache Kafka / RabbitMQ | Kafka — для стриминга, RabbitMQ — для простоты |
| **Оркестрация** | Apache Airflow | Планирование, мониторинг, retry-логика |
| **API** | FastAPI + Uvicorn | Асинхронность, авто-документация, валидация |
| **Асинхронные задачи** | Celery + Redis | Фоновая обработка вне Spark-пайплайнов |
| **БД** | PostgreSQL 14+ | Надёжное хранение метаданных и результатов |
| **Object Storage** | MinIO / S3 | Хранение исходных файлов и артефактов |
| **Контейнеризация** | Docker + Docker Compose | Изоляция, воспроизводимость, деплой |
| **Логирование** | structlog + ELK (опционально) | Структурированные логи для мониторинга |
| **Конфигурация** | pydantic-settings + .env | Типизированная конфигурация, валидация |

---

## 5. Базовая структура проекта

```
pd-scanner/
├── docker-compose.yml
├── Makefile
├── requirements.txt
├── pyproject.toml
├── .env.example
│
├── cmd/
│   ├── scanner/
│   │   └── main.py          # Точка входа: сканер + enqueue
│   ├── api/
│   │   └── main.py          # FastAPI: управление и отчёты
│   └── worker/
│       └── main.py          # Celery worker для OCR/парсинга
│
├── src/
│   ├── config/
│   │   ├── settings.py      # Pydantic-based config
│   │   └── loader.py
│   │
│   ├── core/
│   │   ├── logger.py
│   │   ├── exceptions.py
│   │   └── utils.py         # hashing, path utils
│   │
│   ├── scanner/
│   │   ├── file_walker.py   # Рекурсивный обход
│   │   ├── filter.py        # Фильтрация по расширениям
│   │   └── publisher.py     # Отправка задач в Kafka
│   │
│   ├── parsers/
│   │   ├── base.py
│   │   ├── pdf_parser.py
│   │   ├── docx_parser.py
│   │   ├── xlsx_parser.py
│   │   ├── html_parser.py
│   │   └── image_ocr.py     # Tesseract + OpenCV
│   │
│   ├── detectors/
│   │   ├── regex_patterns.py    # Паспорт, СНИЛС, ИНН, телефон
│   │   ├── fuzzy_matcher.py     # Нечёткий поиск ФИО/адресов
│   │   ├── nlp_extractor.py     # Natasha/spaCy для NER
│   │   └── luhn_validator.py    # Валидация карт
│   │
│   ├── classifier/
│   │   ├── base.py
│   │   ├── rule_based.py    # Быстрый старт
│   │   ├── ml_model.py      # scikit-learn / Spark MLlib
│   │   └── categories.py    # УЗ-1, УЗ-2, УЗ-3, УЗ-4
│   │
│   ├── spark/
│   │   ├── session.py       # Инициализация SparkSession
│   │   ├── pipeline.py      # ETL-пайплайн: extract → detect → classify
│   │   └── udfs.py          # Пользовательские функции для Spark
│   │
│   ├── storage/
│   │   ├── postgres.py      # Bun-style repository pattern
│   │   ├── minio.py         # Работа с объектным хранилищем
│   │   └── models.py        # SQLAlchemy/SQLModel модели
│   │
│   ├── reporting/
│   │   ├── generator.py     # JSON/CSV/Markdown отчёты
│   │   └── templates/
│   │
│   └── api/
│       ├── routes/
│       │   ├── health.py
│       │   ├── scan.py
│       │   └── reports.py
│       ├── middleware/
│       │   ├── auth.py
│       │   ├── logging.py
│       │   └── rate_limit.py
│       └── schemas/
│           ├── request.py
│           └── response.py
│
├── airflow/
│   ├── dags/
│   │   └── pd_scan_pipeline.py
│   ├── plugins/
│   └── requirements.txt
│
├── migrations/
│   ├── versions/
│   │   └── 0001_init_schema.py
│   └── env.py
│
├── deploy/
│   ├── docker/
│   │   ├── ocr-service/
│   │   ├── parser-service/
│   │   ├── spark-master/
│   │   ├── spark-worker/
│   │   └── api/
│   └── k8s/
│
└── docs/
    ├── architecture.md
    ├── api.md
    └── deployment.md
```

---

## Границы ответственности модулей

### `config`
- Загрузка переменных окружения через `pydantic-settings`.
- Валидация обязательных полей.
- Экспорт типизированного конфига для всех модулей.

```python
# Пример минимальных настроек
APP_NAME=pd-scanner
APP_ENV=dev
LOG_LEVEL=INFO

# Kafka / RabbitMQ
BROKER_TYPE=kafka
KAFKA_BOOTSTRAP_SERVERS=localhost:9092
KAFKA_TOPIC_RAW_FILES=raw_files

# PostgreSQL
DATABASE_URL=postgresql://user:pass@localhost:5432/pd_scanner

# MinIO / S3
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=...
MINIO_SECRET_KEY=...

# Spark
SPARK_MASTER=local[*]  # или spark://master:7077
SPARK_EXECUTOR_MEMORY=4g

# OCR
TESSERACT_PATH=/usr/bin/tesseract
OCR_LANGS=rus,eng

# Casdoor (опционально, для auth API)
CASDOOR_ENDPOINT=...
CASDOOR_CLIENT_ID=...
```

### `core/logger`
- Инициализация `structlog` или `logging` с JSON-форматом.
- Разные форматы для dev (console) и prod (JSON для ELK).
- Внедрение через dependency injection.

### `scanner`
- Рекурсивный обход директорий (`pathlib`, `os.walk`).
- Фильтрация по расширениям, размеру, дате.
- Хэширование файлов (MD5/SHA256) для дедупликации.
- Публикация задач в брокер (Kafka/RMQ).

### `parsers`
- Абстрактный базовый класс `BaseParser`.
- Реализации для каждого формата:
  - `PDF`: pdfplumber + pdf2image + pytesseract (для сканов).
  - `DOCX`: python-docx.
  - `XLSX`: openpyxl + pandas.
  - `HTML`: BeautifulSoup + html2text.
  - `IMG`: OpenCV (предобработка) + pytesseract.
- Возврат: `ParsedContent(text, metadata, errors)`.

### `detectors`
- **Regex-паттерны** для структурированных ПДн:
  ```python
  PASSPORT_RU = r'\b\d{4}[\s-]?\d{6}\b'
  SNILS = r'\b\d{3}[\s-]?\d{3}[\s-]?\d{3}[\s-]?\d{2}\b'
  INN = r'\b\d{10}\b|\b\d{12}\b'
  PHONE_RU = r'\b(?:\+7|8)[\s\-]?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}\b'
  ```
- **NLP-извлечение** (Natasha/spaCy) для ФИО, адресов, организаций.
- **Fuzzy matching** (rapidfuzz) для нечёткого поиска.
- **Luhn algorithm** для валидации номеров карт.

### `classifier`
- **Rule-based** (быстрый старт):
  ```python
  if passport_found and snils_found:
      return Category.UZ1  # Особо чувствительные
  elif phone_found or email_found:
      return Category.UZ3  # Общедоступные
  ```
- **ML-подход** (качество):
  - Признаки: частота паттернов, ключевые слова, контекст.
  - Модели: LogisticRegression, RandomForest (scikit-learn) или Spark MLlib.
  - Для NER: ruBERT через DeepPavlov (опционально).

### `spark`
- Инициализация `SparkSession` с настройками:
  ```python
  SparkSession.builder \
      .appName("pd-scanner") \
      .config("spark.sql.shuffle.partitions", "200") \
      .config("spark.executor.memory", "4g") \
      .getOrCreate()
  ```
- ETL-пайплайн:
  1. Чтение задач из Kafka / Parquet.
  2. Параллельное извлечение текста (UDF или mapPartitions).
  3. Детекция ПДн (vectorized regex + NLP).
  4. Классификация (ML model broadcast).
  5. Запись результатов в PostgreSQL / Parquet.

### `storage`
- **PostgreSQL**: хранение метаданных, результатов детекции, отчётов.
  - Таблицы: `files`, `detections`, `classifications`, `scan_jobs`.
- **MinIO/S3**: хранение исходных файлов (опционально), артефактов OCR.
- Репозитории по паттерну Repository + Unit of Work.

### `api` (FastAPI)
- Middleware:
  - `request_id` (UUID для трассировки).
  - `structured_logging`.
  - `auth` (Casdoor JWT verification, опционально).
  - `rate_limit` (для публичных эндпоинтов).
- Эндпоинты:
  ```
  GET  /health/live          # Liveness probe
  GET  /health/ready         # Readiness (DB, Kafka, Spark)
  POST /api/v1/scans         # Запуск нового сканирования
  GET  /api/v1/scans/{id}    # Статус задачи
  GET  /api/v1/reports/{id}  # Получение отчёта
  GET  /api/v1/stats         # Агрегированная статистика
  ```

### `airflow`
- DAG для оркестрации:
  ```python
  with DAG("pd_scan_daily", schedule="@daily") as dag:
      scan_files >> extract_text >> detect_pd >> classify >> generate_report
  ```
- Операторы:
  - `PythonOperator` для вызова сервисов.
  - `SparkSubmitOperator` для запуска Spark-джобов.
  - `SlackWebhookOperator` для уведомлений.