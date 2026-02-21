export type VoiceResponseMode = 'auto' | 'brief' | 'chat' | 'story' | 'story_max';
export type BackendVoiceProfile = Exclude<VoiceResponseMode, 'auto'>;

export interface VoiceResponseOption {
  value: VoiceResponseMode;
  label: string;
  description: string;
}

export const VOICE_RESPONSE_OPTIONS: VoiceResponseOption[] = [
  { value: 'auto', label: 'Auto', description: 'Latency-aware automatic profile' },
  { value: 'brief', label: 'Brief', description: 'Fast and concise replies' },
  { value: 'chat', label: 'Chat', description: 'Balanced conversational replies' },
  { value: 'story', label: 'Story', description: 'Richer narrative replies' },
  { value: 'story_max', label: 'Story Max', description: 'Maximum narrative detail' },
];

export function toBackendVoiceProfile(mode: VoiceResponseMode): BackendVoiceProfile | undefined {
  return mode === 'auto' ? undefined : mode;
}
