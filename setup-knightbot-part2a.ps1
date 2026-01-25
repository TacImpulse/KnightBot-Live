# ═══════════════════════════════════════════════════════════════════════════════
# KNIGHTBOT SETUP - PART 2A (Frontend Config + Core)
# Save as: setup-knightbot-part2a.ps1
# ═══════════════════════════════════════════════════════════════════════════════
$BaseDir = "F:\KnightBot\frontend"
New-Item -ItemType Directory -Force -Path "$BaseDir\src\app","$BaseDir\src\lib","$BaseDir\src\components" | Out-Null
Write-Host "`n🛡️ KNIGHTBOT PART 2A - Config & Core`n" -ForegroundColor Cyan
# ─── PACKAGE.JSON ───
@'
{
  "name": "knightbot-frontend",
  "version": "1.0.0",
  "private": true,
  "scripts": { "dev": "next dev -p 3000", "build": "next build", "start": "next start -p 3000" },
  "dependencies": {
    "next": "14.2.5", "react": "18.3.1", "react-dom": "18.3.1",
    "lucide-react": "0.400.0", "zustand": "4.5.4", "react-markdown": "9.0.1",
    "remark-gfm": "4.0.0", "rehype-highlight": "7.0.0", "framer-motion": "11.3.0"
  },
  "devDependencies": {
    "@types/node": "20.14.10", "@types/react": "18.3.3", "typescript": "5.5.3",
    "tailwindcss": "3.4.4", "postcss": "8.4.39", "autoprefixer": "10.4.19"
  }
}
'@ | Set-Content "$BaseDir\package.json" -Encoding UTF8
# ─── TSCONFIG.JSON ───
@'
{
  "compilerOptions": {
    "lib": ["dom", "dom.iterable", "esnext"], "allowJs": true, "skipLibCheck": true,
    "strict": true, "noEmit": true, "esModuleInterop": true, "module": "esnext",
    "moduleResolution": "bundler", "resolveJsonModule": true, "isolatedModules": true,
    "jsx": "preserve", "incremental": true, "plugins": [{ "name": "next" }],
    "paths": { "@/*": ["./src/*"] }, "target": "ES2017"
  },
  "include": ["next-env.d.ts", "**/*.ts", "**/*.tsx", ".next/types/**/*.ts"],
  "exclude": ["node_modules"]
}
'@ | Set-Content "$BaseDir\tsconfig.json" -Encoding UTF8
# ─── NEXT.CONFIG.JS ───
@'
/** @type {import('next').NextConfig} */
module.exports = {
  reactStrictMode: true,
  async rewrites() {
    return [
      { source: '/api/knight/:path*', destination: 'http://localhost:8100/:path*' },
      { source: '/api/stt/:path*', destination: 'http://localhost:8070/:path*' },
      { source: '/api/tts/:path*', destination: 'http://localhost:8060/:path*' },
    ];
  },
};
'@ | Set-Content "$BaseDir\next.config.js" -Encoding UTF8
# ─── TAILWIND.CONFIG.JS ───
@'
/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./src/**/*.{js,ts,jsx,tsx,mdx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        knight: { bg: '#0a0a14', surface: '#12121c', border: '#1e1e2e', cyan: '#22d3ee', purple: '#a855f7', orange: '#f97316', yellow: '#facc15', text: '#e2e8f0', muted: '#64748b' }
      }
    }
  },
  plugins: [],
};
'@ | Set-Content "$BaseDir\tailwind.config.js" -Encoding UTF8
# ─── POSTCSS.CONFIG.JS ───
'module.exports = { plugins: { tailwindcss: {}, autoprefixer: {} } };' | Set-Content "$BaseDir\postcss.config.js" -Encoding UTF8
# ─── GLOBALS.CSS ───
@'
@tailwind base;
@tailwind components;
@tailwind utilities;
:root { --knight-bg: #0a0a14; --knight-surface: #12121c; --knight-border: #1e1e2e; --knight-cyan: #22d3ee; --knight-purple: #a855f7; --knight-orange: #f97316; }
html, body { background: var(--knight-bg); color: #e2e8f0; font-family: system-ui, sans-serif; height: 100%; }
::-webkit-scrollbar { width: 8px; }
::-webkit-scrollbar-track { background: var(--knight-bg); }
::-webkit-scrollbar-thumb { background: var(--knight-border); border-radius: 4px; }
pre { background: var(--knight-surface) !important; border: 1px solid var(--knight-border); border-radius: 8px; padding: 1rem; overflow-x: auto; }
code { font-family: monospace; font-size: 0.9em; }
.gradient-text { background: linear-gradient(135deg, var(--knight-cyan), var(--knight-purple)); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
.voice-bar { width: 4px; height: 20px; background: linear-gradient(to top, var(--knight-cyan), var(--knight-purple)); border-radius: 2px; animation: vw 1.2s ease-in-out infinite; }
.voice-bar:nth-child(2) { animation-delay: 0.1s; } .voice-bar:nth-child(3) { animation-delay: 0.2s; } .voice-bar:nth-child(4) { animation-delay: 0.3s; }
@keyframes vw { 0%, 100% { transform: scaleY(1); } 50% { transform: scaleY(2); } }
'@ | Set-Content "$BaseDir\src\app\globals.css" -Encoding UTF8
# ─── LAYOUT.TSX ───
@'
import './globals.css';
export const metadata = { title: 'KnightBot - Ultimate Voice Bridge', description: 'Your sharp-witted AI companion' };
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return <html lang="en" className="dark"><body className="bg-knight-bg text-knight-text">{children}</body></html>;
}
'@ | Set-Content "$BaseDir\src\app\layout.tsx" -Encoding UTF8
# ─── STORE.TS ───
@'
import { create } from 'zustand';
export interface Message { id: string; role: 'user' | 'assistant'; content: string; timestamp: Date; isStreaming?: boolean; isError?: boolean; }
interface State {
  messages: Message[];
  addMessage: (m: Message) => void;
  updateMessage: (id: string, u: Partial<Message>) => void;
  clearMessages: () => void;
  isVoiceMode: boolean; setVoiceMode: (v: boolean) => void;
  isListening: boolean; setListening: (v: boolean) => void;
  isSpeaking: boolean; setSpeaking: (v: boolean) => void;
  isMuted: boolean; setMuted: (v: boolean) => void;
}
export const useStore = create<State>((set) => ({
  messages: [],
  addMessage: (m) => set((s) => ({ messages: [...s.messages, m] })),
  updateMessage: (id, u) => set((s) => ({ messages: s.messages.map((m) => m.id === id ? { ...m, ...u } : m) })),
  clearMessages: () => set({ messages: [] }),
  isVoiceMode: false, setVoiceMode: (v) => set({ isVoiceMode: v }),
  isListening: false, setListening: (v) => set({ isListening: v }),
  isSpeaking: false, setSpeaking: (v) => set({ isSpeaking: v }),
  isMuted: false, setMuted: (v) => set({ isMuted: v }),
}));
'@ | Set-Content "$BaseDir\src\lib\store.ts" -Encoding UTF8
# ─── API.TS ───
@'
export async function sendMessage(message: string) {
  const r = await fetch('/api/knight/chat', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ message }) });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}
export async function synthesizeSpeech(text: string): Promise<Blob> {
  const r = await fetch('/api/tts/synthesize', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ text, exaggeration: 0.5 }) });
  if (!r.ok) throw new Error('TTS failed');
  return r.blob();
}
export async function transcribeAudio(blob: Blob) {
  const fd = new FormData(); fd.append('audio', blob, 'rec.webm');
  const r = await fetch('/api/stt/transcribe', { method: 'POST', body: fd });
  return r.json();
}
export async function checkHealth() {
  const h = { knight: false, stt: false, tts: false };
  try { h.knight = (await fetch('/api/knight/health')).ok; } catch {}
  try { h.stt = (await fetch('/api/stt/health')).ok; } catch {}
  try { h.tts = (await fetch('/api/tts/health')).ok; } catch {}
  return h;
}
'@ | Set-Content "$BaseDir\src\lib\api.ts" -Encoding UTF8
Write-Host "✓ Part 2A complete - config and core files" -ForegroundColor Green
Write-Host "  Next: Run setup-knightbot-part2b.ps1 for components`n"
Read-Host "Press Enter to exit"