import { NextResponse } from 'next/server';

// Check both STT targets.
function withPath(url: string, path: string): string {
  const trimmed = url.replace(/\/+$/, '');
  return trimmed.endsWith(path) ? trimmed : `${trimmed}${path}`;
}

const primaryBase =
  process.env.STT_PRIMARY_URL ||
  process.env.STT_URL ||
  'http://localhost:8071';

const fallbackBase =
  process.env.STT_FALLBACK_URL ||
  (primaryBase.includes(':8071') ? 'http://localhost:8070' : 'http://localhost:8071');

const PRIMARY_STT_HEALTH_URL =
  process.env.STT_PRIMARY_HEALTH_URL || withPath(primaryBase.replace(/\/transcribe$/, ''), '/health');

const FALLBACK_STT_HEALTH_URL =
  process.env.STT_FALLBACK_HEALTH_URL || withPath(fallbackBase.replace(/\/transcribe$/, ''), '/health');

interface ServiceHealth {
  service: string;
  status: string;
  latency?: number;
  error?: string;
  model?: string;
  device?: string;
}

async function checkService(url: string, serviceName: string): Promise<ServiceHealth> {
  const start = Date.now();
  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 5000);
    
    const response = await fetch(url, { signal: controller.signal });
    clearTimeout(timeout);
    
    const latency = Date.now() - start;
    const data = await response.json();
    
    return {
      service: serviceName,
      status: response.ok ? 'healthy' : 'degraded',
      latency,
      ...data
    };
  } catch (error) {
    return {
      service: serviceName,
      status: 'unavailable',
      error: error instanceof Error ? error.message : 'Connection failed'
    };
  }
}

export async function GET() {
  // Check both services in parallel
  const [primaryService, fallbackService] = await Promise.all([
    checkService(PRIMARY_STT_HEALTH_URL, 'primary'),
    checkService(FALLBACK_STT_HEALTH_URL, 'fallback')
  ]);

  // Determine overall status
  const services = [primaryService, fallbackService];
  const healthyCount = services.filter(s => s.status === 'healthy').length;
  const selectedService = primaryService.status === 'healthy' ? primaryService : fallbackService;

  return NextResponse.json({
    status: healthyCount > 0 ? 'healthy' : 'unavailable',
    primary: selectedService.service,
    services,
    model: selectedService.model || 'unknown',
    device: selectedService.device || 'unknown'
  });
}
