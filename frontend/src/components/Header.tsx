'use client';
import { Menu, Square, Volume2, VolumeX, Settings } from 'lucide-react';
import { useStore } from '@/lib/store';
import { useState, useEffect } from 'react';
import { checkHealth } from '@/lib/api';
interface Props { onMenuClick: () => void; onInterrupt: () => void; isSpeaking: boolean; }
export function Header({ onMenuClick, onInterrupt, isSpeaking }: Props) {
  const { isMuted, setMuted } = useStore();
  const [health, setHealth] = useState({ knight: false, stt: false, tts: false });
  useEffect(() => {
    const check = async () => setHealth(await checkHealth());
    check();
    const i = setInterval(check, 30000);
    return () => clearInterval(i);
  }, []);
  return (
    <header className="h-16 border-b border-knight-border bg-knight-surface/50 backdrop-blur flex items-center justify-between px-4">
      <div className="flex items-center gap-4">
        <button onClick={onMenuClick} className="p-2 hover:bg-knight-border rounded-lg lg:hidden">
          <Menu className="w-5 h-5" />
        </button>
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-full bg-gradient-to-br from-knight-cyan to-knight-purple flex items-center justify-center">
            <span className="text-lg font-bold">K</span>
          </div>
          <div>
            <h1 className="font-semibold gradient-text">KnightBot</h1>
            <p className="text-xs text-knight-muted">Ultimate Voice Bridge</p>
          </div>
        </div>
      </div>
      <div className="flex items-center gap-2">
        <div className="hidden sm:flex items-center gap-2 mr-4">
          {(['knight','stt','tts'] as const).map(k => (
            <div key={k} className="flex items-center gap-1.5">
              <div className={`w-2 h-2 rounded-full ${health[k] ? 'bg-green-400' : 'bg-knight-muted'}`} />
              <span className="text-xs text-knight-muted uppercase">{k}</span>
            </div>
          ))}
        </div>
        {isSpeaking && (
          <button onClick={onInterrupt} className="flex items-center gap-2 px-3 py-2 bg-red-500/20 text-red-400 rounded-lg hover:bg-red-500/30">
            <Square className="w-4 h-4 fill-current" /><span className="text-sm">Stop</span>
          </button>
        )}
        <button onClick={() => setMuted(!isMuted)} className={`p-2 rounded-lg ${isMuted ? 'bg-knight-orange/20 text-knight-orange' : 'hover:bg-knight-border'}`}>
          {isMuted ? <VolumeX className="w-5 h-5" /> : <Volume2 className="w-5 h-5" />}
        </button>
        <button onClick={() => useStore.getState().setSettingsOpen(true)} className="p-2 hover:bg-knight-border rounded-lg"><Settings className="w-5 h-5" /></button>
      </div>
    </header>
  );
}
