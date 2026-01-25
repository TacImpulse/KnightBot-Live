'use client';
import { X, Plus, MessageSquare, Trash2, Settings, Keyboard } from 'lucide-react';
import { useStore } from '@/lib/store';
import { useState, useEffect } from 'react';
import { getVoices, getConfig } from '@/lib/api';

interface Props { isOpen: boolean; onClose: () => void; }

export function Sidebar({ isOpen, onClose }: Props) {
  const { clearMessages, currentVoice, setVoice, systemPrompt, setSystemPrompt, isSettingsOpen, setSettingsOpen } = useStore();
  const [voices, setVoices] = useState<string[]>([]);
  const [tempPrompt, setTempPrompt] = useState('');

  useEffect(() => {
    if (isSettingsOpen) {
      getVoices().then(data => {
        setVoices(data.voices);
        if (!currentVoice && data.default) setVoice(data.default);
      });
      if (!systemPrompt) {
        getConfig().then(data => {
          setSystemPrompt(data.system_prompt);
          setTempPrompt(data.system_prompt);
        });
      } else {
        setTempPrompt(systemPrompt);
      }
    }
  }, [isSettingsOpen, currentVoice, setVoice, systemPrompt, setSystemPrompt]);

  const saveSettings = () => {
    setSystemPrompt(tempPrompt);
    setSettingsOpen(false);
  };

  if (isSettingsOpen) {
    return (
      <div className="fixed inset-0 bg-knight-bg/95 backdrop-blur-xl z-50 flex items-center justify-center p-4">
        <div className="bg-knight-surface border border-knight-border rounded-2xl w-full max-w-2xl max-h-[90vh] overflow-hidden flex flex-col shadow-2xl">
          <div className="flex items-center justify-between p-6 border-b border-knight-border">
            <h2 className="text-xl font-semibold flex items-center gap-2">
              <Settings className="w-5 h-5 text-knight-cyan" /> Settings
            </h2>
            <button onClick={() => setSettingsOpen(false)} className="p-2 hover:bg-knight-border rounded-lg"><X className="w-5 h-5" /></button>
          </div>
          <div className="flex-1 overflow-y-auto p-6 space-y-6">
            <section>
              <h3 className="text-sm font-medium text-knight-muted mb-3 uppercase tracking-wider">Voice Persona</h3>
              <div className="space-y-4">
                <div>
                  <label className="block text-sm mb-2">TTS Voice Model</label>
                  <select 
                    value={currentVoice || ''} 
                    onChange={(e) => setVoice(e.target.value)}
                    className="w-full bg-knight-bg border border-knight-border rounded-xl p-3 outline-none focus:border-knight-cyan"
                  >
                    <option value="knight_voice">Default (Knight)</option>
                    {voices.map(v => <option key={v} value={v}>{v}</option>)}
                  </select>
                </div>
                <div>
                  <label className="block text-sm mb-2">System Prompt (Persona)</label>
                  <textarea 
                    value={tempPrompt}
                    onChange={(e) => setTempPrompt(e.target.value)}
                    className="w-full h-40 bg-knight-bg border border-knight-border rounded-xl p-3 outline-none focus:border-knight-cyan resize-none text-sm font-mono"
                    placeholder="You are Knight..."
                  />
                </div>
              </div>
            </section>
            
            <section>
              <h3 className="text-sm font-medium text-knight-muted mb-3 uppercase tracking-wider">Shortcuts</h3>
              <div className="grid grid-cols-2 gap-4">
                <div className="flex justify-between p-3 bg-knight-bg rounded-lg border border-knight-border">
                  <span className="text-sm">Toggle Voice Mode</span>
                  <code className="text-xs bg-knight-surface px-2 py-1 rounded text-knight-cyan">Ctrl + V</code>
                </div>
                <div className="flex justify-between p-3 bg-knight-bg rounded-lg border border-knight-border">
                  <span className="text-sm">Stop Listening</span>
                  <code className="text-xs bg-knight-surface px-2 py-1 rounded text-knight-cyan">Space</code>
                </div>
                <div className="flex justify-between p-3 bg-knight-bg rounded-lg border border-knight-border">
                  <span className="text-sm">Interrupt</span>
                  <code className="text-xs bg-knight-surface px-2 py-1 rounded text-knight-cyan">Esc</code>
                </div>
                <div className="flex justify-between p-3 bg-knight-bg rounded-lg border border-knight-border">
                  <span className="text-sm">Send Message</span>
                  <code className="text-xs bg-knight-surface px-2 py-1 rounded text-knight-cyan">Enter</code>
                </div>
              </div>
            </section>
          </div>
          <div className="p-6 border-t border-knight-border bg-knight-bg/50 flex justify-end gap-3">
            <button onClick={() => setSettingsOpen(false)} className="px-4 py-2 hover:bg-knight-border rounded-lg text-sm">Cancel</button>
            <button onClick={saveSettings} className="px-6 py-2 bg-knight-cyan text-black font-medium rounded-lg text-sm hover:bg-knight-cyan/90">Save Changes</button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <>
      {isOpen && <div className="fixed inset-0 bg-black/50 z-40 lg:hidden" onClick={onClose} />}
      <aside className={`fixed lg:static inset-y-0 left-0 z-50 w-72 bg-knight-surface border-r border-knight-border transform transition-transform ${isOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'} flex flex-col`}>
        <div className="h-16 border-b border-knight-border flex items-center justify-between px-4">
          <span className="font-semibold">Conversations</span>
          <button onClick={onClose} className="p-2 hover:bg-knight-border rounded-lg lg:hidden"><X className="w-5 h-5" /></button>
        </div>
        <div className="p-3 space-y-2">
          <button onClick={() => { clearMessages(); onClose(); }} className="w-full flex items-center gap-2 px-4 py-3 bg-gradient-to-r from-knight-cyan/20 to-knight-purple/20 hover:from-knight-cyan/30 hover:to-knight-purple/30 border border-knight-border rounded-lg transition-all">
            <Plus className="w-5 h-5 text-knight-cyan" /><span>New Chat</span>
          </button>
          <button onClick={() => { setSettingsOpen(true); onClose(); }} className="w-full flex items-center gap-2 px-4 py-3 hover:bg-knight-border rounded-lg text-knight-muted hover:text-knight-text transition-all">
            <Settings className="w-5 h-5" /><span>Settings & Shortcuts</span>
          </button>
        </div>
        <div className="flex-1 overflow-y-auto p-3">
          <p className="text-center text-knight-muted text-sm py-8">Chat history coming soon</p>
        </div>
        <div className="p-3 border-t border-knight-border">
          <button onClick={clearMessages} className="w-full flex items-center gap-2 px-3 py-2 text-red-400 hover:bg-red-500/10 rounded-lg">
            <Trash2 className="w-4 h-4" /><span className="text-sm">Clear Current Chat</span>
          </button>
        </div>
      </aside>
    </>
  );
}
