import { create } from 'zustand';
import type { VoiceResponseMode } from '@/lib/voiceProfiles';
export interface Message { 
  id: string; 
  role: 'user' | 'assistant'; 
  content: string; 
  timestamp: Date; 
  isStreaming?: boolean; 
  isError?: boolean;
  images?: string[]; // Base64 image data for display
  parentId?: string; // For branching conversations
  isBranch?: boolean;
}
interface State {
  messages: Message[];
  addMessage: (m: Message) => void;
  updateMessage: (id: string, u: Partial<Message>) => void;
  deleteMessage: (id: string) => void;
  clearMessages: () => void;
  isVoiceMode: boolean; setVoiceMode: (v: boolean) => void;
  isListening: boolean; setListening: (v: boolean) => void;
  isSpeaking: boolean; setSpeaking: (v: boolean) => void;
  isMuted: boolean; setMuted: (v: boolean) => void;
  
  // Settings
  currentVoice: string | null; setVoice: (v: string | null) => void;
  systemPrompt: string | null; setSystemPrompt: (p: string | null) => void;
  voiceResponseMode: VoiceResponseMode; setVoiceResponseMode: (mode: VoiceResponseMode) => void;
  
  // UI State
  isSettingsOpen: boolean; setSettingsOpen: (v: boolean) => void;
}
export const useStore = create<State>((set) => ({
  messages: [],
  addMessage: (m) => set((s) => ({ messages: [...s.messages, m] })),
  updateMessage: (id, u) => set((s) => ({ messages: s.messages.map((m) => m.id === id ? { ...m, ...u } : m) })),
  deleteMessage: (id) => set((s) => ({ messages: s.messages.filter((m) => m.id !== id) })),
  clearMessages: () => set({ messages: [] }),
  isVoiceMode: false, setVoiceMode: (v) => set({ isVoiceMode: v }),
  isListening: false, setListening: (v) => set({ isListening: v }),
  isSpeaking: false, setSpeaking: (v) => set({ isSpeaking: v }),
  isMuted: false, setMuted: (v) => set({ isMuted: v }),
  
  currentVoice: null, setVoice: (v) => set({ currentVoice: v }),
  systemPrompt: null, setSystemPrompt: (p) => set({ systemPrompt: p }),
  voiceResponseMode: 'auto', setVoiceResponseMode: (mode) => set({ voiceResponseMode: mode }),
  
  isSettingsOpen: false, setSettingsOpen: (v) => set({ isSettingsOpen: v }),
}));
