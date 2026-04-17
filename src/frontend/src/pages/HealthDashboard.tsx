import { ThemeProvider } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';
import Box from '@mui/material/Box';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';
import Container from '@mui/material/Container';
import { theme } from '../theme';
import { useHealthCheck } from '../hooks/useHealthCheck';
import { InfrastructureGrid } from '../components/InfrastructureGrid';

export default function HealthDashboard() {
  const {
    data,
    loading,
    error,
    lastUpdated,
    refresh,
  } = useHealthCheck({ interval: 30000 });

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <Box sx={{ minHeight: '100vh', bgcolor: 'background.default' }}>
        {/* Header */}
        <Box
          sx={{
            py: 4,
            bgcolor: 'primary.main',
            color: 'common.white',
            boxShadow: '0 8px 24px rgba(0,0,0,0.12)',
          }}
        >
          <Container maxWidth="xl">
            <Stack direction="row" spacing={2} alignItems="center">
              <Stack>
                <Typography variant="h4" fontWeight={700}>
                  PD Scanner
                </Typography>
                <Typography variant="body1" sx={{ opacity: 0.88 }}>
                  Мониторинг инфраструктуры
                </Typography>
              </Stack>
            </Stack>
          </Container>
        </Box>

        {/* Content */}
        <Container maxWidth="xl" sx={{ py: 4 }}>
          <InfrastructureGrid
            data={data}
            loading={loading}
            error={error}
            onRefresh={refresh}
            lastUpdated={lastUpdated}
          />
        </Container>

        {/* Footer */}
        <Box component="footer" sx={{ py: 3, textAlign: 'center', color: 'text.secondary' }}>
          <Typography variant="caption">
            PD Scanner Health Dashboard • v1.0.0
          </Typography>
        </Box>
      </Box>
    </ThemeProvider>
  );
}