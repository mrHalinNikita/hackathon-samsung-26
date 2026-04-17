import Card from '@mui/material/Card';
import CardContent from '@mui/material/CardContent';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';
import Avatar from '@mui/material/Avatar';
import Box from '@mui/material/Box';
import type { ServiceHealth, ServiceMeta } from '../types/health';
import { StatusBadge } from './StatusBadge';

interface HealthCardProps {
  result: ServiceHealth;
  meta: ServiceMeta;
}

export function HealthCard({ result, meta }: HealthCardProps) {
  const statusColors = {
    ok: 'success',
    degraded: 'warning',
    error: 'error',
    unknown: 'default',
  } as const;
  
  const color = statusColors[result.status] || 'default';
  
  const colorConfig: Record<string, { main: string; light: string }> = {
    success: { main: '#2e7d32', light: '#4caf50' },
    warning: { main: '#ed6c02', light: '#ff9800' },
    error: { main: '#d32f2f', light: '#ef5350' },
    default: { main: '#757575', light: '#9e9e9e' },
  };
  
  const colorData = colorConfig[color];
  
  return (
    <Card>
      <CardContent>
        <Stack spacing={2}>
          <Stack direction="row" spacing={2} alignItems="center">
            <Avatar
              sx={{
                width: 48,
                height: 48,
                bgcolor: `${colorData.main}1F`,
                color: colorData.main,
              }}
            >
            </Avatar>
            <Box sx={{ flexGrow: 1 }}>
              <Typography variant="subtitle1" fontWeight={600}>
                {meta.label}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                {meta.description}
              </Typography>
            </Box>
            <StatusBadge status={result.status} />
          </Stack>
          
          <Stack spacing={1}>
            <Typography variant="body2" color="text.secondary">
              {result.message}
            </Typography>
            {result.response_time_ms != null && (
              <Typography variant="caption" color="text.secondary">
                Время ответа: {result.response_time_ms} мс
              </Typography>
            )}
          </Stack>
          
          {meta.url && result.status === 'ok' && (
            <Typography 
              variant="caption" 
              component="a" 
              href={meta.url} 
              target="_blank" 
              rel="noopener noreferrer"
              sx={{ 
                color: 'primary.main',
                textDecoration: 'none',
                '&:hover': { textDecoration: 'underline' },
              }}
            >
              Открыть панель управления
            </Typography>
          )}
        </Stack>
      </CardContent>
    </Card>
  );
}