import { NextRequest, NextResponse } from 'next/server';

// Support both Faster Whisper (8071) and Parakeet (8070).
// STT_PRIMARY_URL/STT_FALLBACK_URL override defaults when needed.
const PRIMARY_STT_URL =
  process.env.STT_PRIMARY_URL ||
  process.env.STT_URL ||
  'http://localhost:8071/transcribe';

const FALLBACK_STT_URL =
  process.env.STT_FALLBACK_URL ||
  (PRIMARY_STT_URL.includes(':8071')
    ? 'http://localhost:8070/transcribe'
    : 'http://localhost:8071/transcribe');

function withPath(url: string, path: string): string {
  const trimmed = url.replace(/\/+$/, '');
  return trimmed.endsWith(path) ? trimmed : `${trimmed}${path}`;
}

const PRIMARY_TRANSCRIBE_URL = withPath(PRIMARY_STT_URL, '/transcribe');
const FALLBACK_TRANSCRIBE_URL = withPath(FALLBACK_STT_URL, '/transcribe');

function cloneFormData(source: FormData): FormData {
  const copy = new FormData();
  for (const [key, value] of source.entries()) {
    if (typeof value === 'string') {
      copy.append(key, value);
    } else {
      copy.append(key, value, value.name);
    }
  }
  return copy;
}

export async function POST(req: NextRequest) {
  let lastError: Error | null = null;
  const formData = await req.formData();
  
  // Try Faster Whisper first (preferred)
  try {
    const response = await fetch(PRIMARY_TRANSCRIBE_URL, {
      method: 'POST',
      body: cloneFormData(formData),
      signal: AbortSignal.timeout(30000),
    });
    
    if (response.ok) {
      const data = await response.json();
      return NextResponse.json({ ...data, service: 'primary' });
    }
    lastError = new Error(`Faster Whisper: ${response.status}`);
  } catch (error) {
    lastError = error as Error;
    console.warn('Primary STT unavailable, trying fallback...');
  }

  // Fallback to Parakeet
  try {
    const response = await fetch(FALLBACK_TRANSCRIBE_URL, {
      method: 'POST',
      body: cloneFormData(formData),
      signal: AbortSignal.timeout(60000),  // Parakeet is slower
    });
    
    if (response.ok) {
      const data = await response.json();
      return NextResponse.json({ ...data, service: 'fallback' });
    }
    lastError = new Error(`Parakeet: ${response.status}`);
  } catch (error) {
    lastError = error as Error;
  }

  return NextResponse.json(
    { error: 'All STT services unavailable', details: lastError?.message },
    { status: 503 }
  );
}
