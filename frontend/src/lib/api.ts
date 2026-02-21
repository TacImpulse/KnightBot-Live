import type { BackendVoiceProfile } from './voiceProfiles';

const KNIGHT_API = '/api/knight';
const STT_API = '/api/stt';
const TTS_API = '/api/tts';

export async function sendMessage(
  message: string,
  voiceId?: string,
  systemPrompt?: string,
  images?: string[],
  includeAudio: boolean = false,
  voiceProfile?: BackendVoiceProfile,
  timeoutMs: number = 300000
) {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);
  
  try {
    const r = await fetch(`${KNIGHT_API}/chat`, { 
      method: 'POST',
      headers: { 'Content-Type': 'application/json' }, 
      body: JSON.stringify({
        message,
        voice_id: voiceId,
        system_prompt: systemPrompt,
        images,
        include_audio: includeAudio,
        voice_profile: voiceProfile,
      }),
      signal: controller.signal
    });
    clearTimeout(timeoutId);
    if (!r.ok) throw new Error(await r.text());
    return r.json();
  } catch (error) {
    clearTimeout(timeoutId);
    if (error instanceof Error && error.name === 'AbortError') {
      throw new Error('Request timed out. The model may be taking too long to respond.');
    }
    throw error;
  }
}

export async function synthesizeSpeech(text: string, exaggeration = 0.5, voiceId?: string): Promise<Blob> {
  const r = await fetch(`${TTS_API}/synthesize`, { 
    method: 'POST',
    headers: { 'Content-Type': 'application/json' }, 
    body: JSON.stringify({ text, exaggeration, voice_id: voiceId }) 
  });
  if (!r.ok) throw new Error('TTS failed');
  return r.blob();
}

export async function transcribeAudio(blob: Blob) {
  const fd = new FormData(); fd.append('audio', blob, 'rec.wav');
  const r = await fetch(`${STT_API}/transcribe`, { method: 'POST', body: fd });
  return r.json();
}

export async function checkHealth() {
  const h = { knight: false, stt: false, tts: false };
  try { h.knight = (await fetch(`${KNIGHT_API}/health`)).ok; } catch {}
  try { h.stt = (await fetch(`${STT_API}/health`)).ok; } catch {}
  try { h.tts = (await fetch(`${TTS_API}/health`)).ok; } catch {}
  return h;
}

export async function getVoices() {
  const r = await fetch(`${TTS_API}/voices`);
  if (!r.ok) return { voices: [], default: null };
  return r.json();
}

export async function uploadVoice(file: File, name?: string) {
  const fd = new FormData();
  fd.append('file', file);
  if (name) fd.append('name', name);
  const r = await fetch(`${TTS_API}/voices/upload`, { method: 'POST', body: fd });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function uploadAvatar(voiceId: string, file: File) {
  const fd = new FormData();
  fd.append('file', file);
  const r = await fetch(`${TTS_API}/voices/${voiceId}/avatar`, { method: 'POST', body: fd });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function renameVoice(voiceId: string, newName: string) {
  const r = await fetch(`${TTS_API}/voices/${voiceId}/rename?new_name=${encodeURIComponent(newName)}`, { method: 'POST' });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function selectVoice(voiceId: string) {
  const r = await fetch(`${TTS_API}/voices/select?voice_id=${encodeURIComponent(voiceId)}`, { method: 'POST' });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function deleteVoice(voiceId: string) {
  const r = await fetch(`${TTS_API}/voices/${voiceId}`, { method: 'DELETE' });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function getLiveKitToken(roomName: string, participantName: string) {
  const r = await fetch(`${KNIGHT_API}/token`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ room_name: roomName, participant_name: participantName })
  });
  if (!r.ok) {
    // Preserve server-provided error details to make debugging easier.
    let details = '';
    try {
      details = await r.text();
    } catch {
      details = '';
    }
    const msg = details?.trim() ? `Failed to get LiveKit token: ${details}` : 'Failed to get LiveKit token';
    throw new Error(msg);
  }
  return r.json();
}

export async function getConfig() {
  const r = await fetch(`${KNIGHT_API}/config`);
  if (!r.ok) return { system_prompt: '' };
  return r.json();
}
