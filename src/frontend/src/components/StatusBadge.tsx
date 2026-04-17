import { Chip, type ChipProps } from '@mui/material';
import type { ServiceStatus } from '../types/health';

interface StatusBadgeProps {
  status: ServiceStatus;
  size?: 'small' | 'medium';
}

const statusConfig: Record<ServiceStatus, { label: string; color: ChipProps['color'] }> = {
  ok: { label: 'Работает', color: 'success' },
  degraded: { label: 'Деградирован', color: 'warning' },
  error: { label: 'Ошибка', color: 'error' },
  unknown: { label: 'Неизвестно', color: 'default' },
};

export function StatusBadge({ status, size = 'medium' }: StatusBadgeProps) {
  const config = statusConfig[status];
  
  return (
    <Chip
      label={config.label}
      color={config.color}
      size={size}
      variant="filled"
      sx={{ fontWeight: 600, borderRadius: 2 }}
    />
  );
}