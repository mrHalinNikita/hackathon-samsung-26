import axios from 'axios';
import type { HealthCheckResponse } from '../types/health';

export const api = axios.create({
  baseURL: '/api/v1',
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json',
  },
});

export const healthApi = {
  getAll: async (): Promise<HealthCheckResponse> => {
    const { data } = await api.get<HealthCheckResponse>('/health');
    return data;
  },
  getService: async (serviceName: string) => {
    const { data } = await api.get(`/health/${serviceName}`);
    return data;
  },
};