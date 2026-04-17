import { useCallback, useEffect, useState } from 'react';
import type { HealthCheckResponse, ServiceStatus } from '../types/health';
import { healthApi } from '../utils/api';

interface UseHealthCheckOptions {
  interval?: number;
  enabled?: boolean;
}

export function useHealthCheck(options: UseHealthCheckOptions = {}) {
  const { interval = 30000, enabled = true } = options;
  
  const [data, setData] = useState<HealthCheckResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  const fetchHealth = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const result = await healthApi.getAll();
      setData(result);
      setLastUpdated(new Date());
    } catch (err) {
      setError(err instanceof Error ? err : new Error('Не удалось загрузить данные'));
    } finally {
      setLoading(false);
    }
  }, []);

  const refresh = useCallback(() => {
    fetchHealth();
  }, [fetchHealth]);

  useEffect(() => {
    if (!enabled) return;
    
    fetchHealth();
    const timer = setInterval(fetchHealth, interval);
    
    return () => clearInterval(timer);
  }, [fetchHealth, interval, enabled]);

  const getOverallStatus = useCallback((): ServiceStatus => {
    if (!data) return 'unknown';
    if (data.services.some(s => s.status === 'error')) return 'error';
    if (data.services.some(s => s.status === 'degraded')) return 'degraded';
    return data.status;
  }, [data]);

  return {
    data,
    loading,
    error,
    lastUpdated,
    refresh,
    overallStatus: getOverallStatus(),
  };
}