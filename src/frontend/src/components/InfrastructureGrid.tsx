import Box from '@mui/material/Box';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';
import LinearProgress from '@mui/material/LinearProgress';
import Alert from '@mui/material/Alert';
import Card from '@mui/material/Card';
import CardContent from '@mui/material/CardContent';
import type { HealthCheckResponse } from '../types/health';
import { SERVICE_META } from '../types/health';
import { HealthCard } from './HealthCard';
import { StatusBadge } from './StatusBadge';

interface InfrastructureGridProps {
  data: HealthCheckResponse | null;
  loading: boolean;
  error: Error | null;
  onRefresh: () => void;
  lastUpdated: Date | null;
}

export function InfrastructureGrid({
  data,
  loading,
  error,
  onRefresh,
  lastUpdated,
}: InfrastructureGridProps) {
  if (loading && !data) {
    return (
      <Box sx={{ p: 3 }}>
        <LinearProgress />
      </Box>
    );
  }
  
  if (error) {
    return (
      <Alert severity="error" sx={{ my: 2 }}>
        Не удалось загрузить данные: {error.message}
        <br />
        <Typography 
          component="button" 
          variant="body2" 
          color="primary" 
          sx={{ background: 'none', border: 'none', cursor: 'pointer', mt: 1 }}
          onClick={onRefresh}
        >
          Повторить попытку
        </Typography>
      </Alert>
    );
  }
  
  if (!data) {
    return (
      <Alert severity="info" sx={{ my: 2 }}>
        Нет данных для отображения
      </Alert>
    );
  }
  
  return (
    <Stack spacing={3}>
      {/* Header */}
      <Stack 
        direction={{ xs: 'column', sm: 'row' }} 
        spacing={2} 
        justifyContent="space-between"
        alignItems={{ xs: 'flex-start', sm: 'center' }}
      >
        <Stack spacing={0.5}>
          <Typography variant="h6">Статус инфраструктуры</Typography>
          <Typography variant="body2" color="text.secondary">
            Последнее обновление:{' '}
            {lastUpdated?.toLocaleTimeString('ru-RU') || '—'}
          </Typography>
        </Stack>
        <Stack direction="row" spacing={2} alignItems="center">
          <StatusBadge status={data.status} />
          <Typography 
            component="button"
            variant="body2"
            color="primary"
            sx={{ background: 'none', border: 'none', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 0.5 }}
            onClick={onRefresh}
            disabled={loading}
          >
            Обновить
          </Typography>
        </Stack>
      </Stack>
      
      {/* Services Grid */}
      <Box
        sx={{
          display: 'grid',
          gap: 2,
          gridTemplateColumns: {
            xs: '1fr',
            sm: 'repeat(2, minmax(0, 1fr))',
            lg: 'repeat(3, minmax(0, 1fr))',
          },
        }}
      >
        {data.services.map((service) => {
          const meta = SERVICE_META[service.name];
          if (!meta) return null;
          
          return (
            <HealthCard 
              key={service.name} 
              result={service} 
              meta={meta} 
            />
          );
        })}
      </Box>
      
      {/* Summary */}
      <Card>
        <CardContent>
          <Stack spacing={2}>
            <Typography variant="subtitle1" fontWeight={600}>
              Сводка
            </Typography>
            <Stack direction="row" spacing={4}>
              <Box>
                <Typography variant="h4" color="success.main">
                  {data.services.filter(s => s.status === 'ok').length}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  Работают
                </Typography>
              </Box>
              <Box>
                <Typography variant="h4" color="warning.main">
                  {data.services.filter(s => s.status === 'degraded').length}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  Деградированы
                </Typography>
              </Box>
              <Box>
                <Typography variant="h4" color="error.main">
                  {data.services.filter(s => s.status === 'error').length}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  Ошибки
                </Typography>
              </Box>
            </Stack>
          </Stack>
        </CardContent>
      </Card>
    </Stack>
  );
}