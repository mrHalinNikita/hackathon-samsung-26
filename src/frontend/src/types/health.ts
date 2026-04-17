export type ServiceStatus = 'ok' | 'degraded' | 'error' | 'unknown';

export interface ServiceHealth {
  name: string;
  status: ServiceStatus;
  message: string;
  response_time_ms?: number | null;
  details?: Record<string, unknown> | null;
}

export interface HealthCheckResponse {
  status: ServiceStatus;
  timestamp: string;
  services: ServiceHealth[];
}

export interface ServiceMeta {
  name: string;
  label: string;
  icon: string;
  description: string;
  port?: number;
  url?: string;
}

export const SERVICE_META: Record<string, ServiceMeta> = {
  postgres: {
    name: 'postgres',
    label: 'PostgreSQL',
    icon: 'solar:database-bold',
    description: 'Основная база данных',
    port: 5432,
  },
  redis: {
    name: 'redis',
    label: 'Redis',
    icon: 'solar:chip-bold',
    description: 'Кэш и очередь задач',
    port: 6379,
  },
  kafka: {
    name: 'kafka',
    label: 'Kafka',
    icon: 'solar:server-bold',
    description: 'Асинхронная очередь сообщений',
    port: 9092,
  },
  'spark-master': {
    name: 'spark-master',
    label: 'Spark Master',
    icon: 'solar:cpu-bold',
    description: 'Координатор распределённой обработки',
    port: 8080,
    url: 'http://localhost:8080',
  },
  ocr: {
    name: 'ocr',
    label: 'OCR Service',
    icon: 'solar:scan-bold',
    description: 'Распознавание текста на изображениях',
    port: 8000,
  },
};