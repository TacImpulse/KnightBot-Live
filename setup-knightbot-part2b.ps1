# ═══════════════════════════════════════════════════════════════════════════════
# KNIGHTBOT SETUP - PART 2B (Components)
# Save as: setup-knightbot-part2b.ps1
# ═══════════════════════════════════════════════════════════════════════════════
$BaseDir = "F:\KnightBot\frontend\src\components"
New-Item -ItemType Directory -Force -Path $BaseDir | Out-Null
Write-Host "`n🛡️ KNIGHTBOT PART 2B - Components`n" -ForegroundColor Cyan
# ─── HEADER.TSX ───
@'
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
        <button className="p-2 hover:bg-knight-border rounded-lg"><Settings className="w-5 h-5" /></button>
      </div>
    </header>
  );
}
'@ | Set-Content "$BaseDir\Header.tsx" -Encoding UTF8
Write-Host "✓ Header.tsx" -ForegroundColor Green
# ─── SIDEBAR.TSX ───
@'
'use client';
import { X, Plus, MessageSquare, Trash2 } from 'lucide-react';
import { useStore } from '@/lib/store';
interface Props { isOpen: boolean; onClose: () => void; }
export function Sidebar({ isOpen, onClose }: Props) {
  const { clearMessages } = useStore();
  return (
    <>
      {isOpen && <div className="fixed inset-0 bg-black/50 z-40 lg:hidden" onClick={onClose} />}
      <aside className={`fixed lg:static inset-y-0 left-0 z-50 w-72 bg-knight-surface border-r border-knight-border transform transition-transform ${isOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'} flex flex-col`}>
        <div className="h-16 border-b border-knight-border flex items-center justify-between px-4">
          <span className="font-semibold">Conversations</span>
          <button onClick={onClose} className="p-2 hover:bg-knight-border rounded-lg lg:hidden"><X className="w-5 h-5" /></button>
        </div>
        <div className="p-3">
          <button onClick={() => { clearMessages(); onClose(); }} className="w-full flex items-center gap-2 px-4 py-3 bg-gradient-to-r from-knight-cyan/20 to-knight-purple/20 hover:from-knight-cyan/30 hover:to-knight-purple/30 border border-knight-border rounded-lg">
            <Plus className="w-5 h-5 text-knight-cyan" /><span>New Chat</span>
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
'@ | Set-Content "$BaseDir\Sidebar.tsx" -Encoding UTF8
Write-Host "✓ Sidebar.tsx" -ForegroundColor Green
# ─── CHATCONTAINER.TSX ───
@'
'use client';
import { useRef, useEffect } from 'react';
import { Message } from '@/lib/store';
import { ChatMessage } from './ChatMessage';
interface Props { messages: Message[]; isLoading: boolean; }
export function ChatContainer({ messages, isLoading }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);
  if (messages.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center p-8">
        <div className="text-center max-w-md">
          <div className="w-20 h-20 mx-auto mb-6 rounded-full bg-gradient-to-br from-knight-cyan to-knight-purple flex items-center justify-center">
            <span className="text-3xl font-bold">K</span>
          </div>
          <h2 className="text-2xl font-semibold mb-2 gradient-text">Hey there!</h2>
          <p className="text-knight-muted">I'm Knight, your sharp-witted AI companion. What can I help you with today?</p>
          <div className="mt-6 flex flex-wrap gap-2 justify-center">
            {['Tell me a joke', 'Help me code', 'Explain something'].map(s => (
              <button key={s} className="px-4 py-2 bg-knight-surface border border-knight-border rounded-full text-sm hover:border-knight-cyan/50 transition-colors">{s}</button>
            ))}
          </div>
        </div>
      </div>
    );
  }
  return (
    <div className="flex-1 overflow-y-auto p-4 space-y-4">
      {messages.map(m => <ChatMessage key={m.id} message={m} />)}
      {isLoading && (
        <div className="flex gap-3 max-w-3xl mx-auto">
          <div className="w-8 h-8 rounded-full bg-gradient-to-br from-knight-cyan to-knight-purple flex items-center justify-center flex-shrink-0">
            <span className="text-sm font-bold">K</span>
          </div>
          <div className="flex gap-1 items-center px-4 py-3 bg-knight-surface rounded-2xl">
            <div className="w-2 h-2 bg-knight-cyan rounded-full animate-bounce" style={{animationDelay:'0ms'}} />
            <div className="w-2 h-2 bg-knight-cyan rounded-full animate-bounce" style={{animationDelay:'150ms'}} />
            <div className="w-2 h-2 bg-knight-cyan rounded-full animate-bounce" style={{animationDelay:'300ms'}} />
          </div>
        </div>
      )}
      <div ref={bottomRef} />
    </div>
  );
}
'@ | Set-Content "$BaseDir\ChatContainer.tsx" -Encoding UTF8
Write-Host "✓ ChatContainer.tsx" -ForegroundColor Green
# ─── CHATMESSAGE.TSX ───
@'
'use client';
import { useState } from 'react';
import { Copy, Check, User, Pencil, Trash2 } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Message } from '@/lib/store';
interface Props { message: Message; }
export function ChatMessage({ message }: Props) {
  const [copied, setCopied] = useState(false);
  const isUser = message.role === 'user';
  const copyToClipboard = async (text: string) => {
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };
  return (
    <div className={`flex gap-3 max-w-3xl mx-auto ${isUser ? 'flex-row-reverse' : ''}`}>
      <div className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 ${isUser ? 'bg-knight-purple' : 'bg-gradient-to-br from-knight-cyan to-knight-purple'}`}>
        {isUser ? <User className="w-4 h-4" /> : <span className="text-sm font-bold">K</span>}
      </div>
      <div className={`group relative max-w-[80%] ${isUser ? 'bg-knight-purple/20 rounded-2xl rounded-tr-md' : 'bg-knight-surface rounded-2xl rounded-tl-md'} px-4 py-3 ${message.isError ? 'border border-red-500/50' : ''}`}>
        {message.isStreaming ? (
          <span className="text-knight-text">{message.content}<span className="animate-pulse">▊</span></span>
        ) : isUser ? (
          <p className="text-knight-text whitespace-pre-wrap">{message.content}</p>
        ) : (
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={{
              pre: ({ children }) => (
                <div className="relative my-2">
                  <button onClick={() => copyToClipboard((children as any)?.props?.children || '')} className="absolute top-2 right-2 p-1.5 bg-knight-border/50 rounded hover:bg-knight-border">
                    {copied ? <Check className="w-4 h-4 text-green-400" /> : <Copy className="w-4 h-4" />}
                  </button>
                  <pre className="overflow-x-auto">{children}</pre>
                </div>
              ),
              code: ({ className, children, ...props }) => {
                const isInline = !className;
                return isInline ? (
                  <code className="bg-knight-border px-1.5 py-0.5 rounded text-knight-cyan text-sm" {...props}>{children}</code>
                ) : (
                  <code className={className} {...props}>{children}</code>
                );
              },
              a: ({ href, children }) => (
                <a href={href} target="_blank" rel="noopener noreferrer" className="text-knight-cyan hover:underline">{children}</a>
              ),
            }}
            className="prose prose-invert prose-sm max-w-none"
          >
            {message.content}
          </ReactMarkdown>
        )}
        {!isUser && !message.isStreaming && (
          <div className="opacity-0 group-hover:opacity-100 transition-opacity absolute -bottom-8 left-0 flex gap-1">
            <button onClick={() => copyToClipboard(message.content)} className="p-1.5 bg-knight-surface border border-knight-border rounded hover:border-knight-cyan/50">
              {copied ? <Check className="w-3 h-3 text-green-400" /> : <Copy className="w-3 h-3" />}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
'@ | Set-Content "$BaseDir\ChatMessage.tsx" -Encoding UTF8
Write-Host "✓ ChatMessage.tsx" -ForegroundColor Green
# ─── INPUTBAR.TSX ───
@'
'use client';
import { useRef, useEffect } from 'react';
import { Send, Mic, MicOff, Paperclip } from 'lucide-react';
interface Props {
  value: string; onChange: (v: string) => void; onSend: () => void;
  onVoiceToggle: () => void; isVoiceMode: boolean; isListening: boolean;
  isLoading: boolean; onStopListening: () => void;
}
export function InputBar({ value, onChange, onSend, onVoiceToggle, isVoiceMode, isListening, isLoading, onStopListening }: Props) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = Math.min(textareaRef.current.scrollHeight, 200) + 'px';
    }
  }, [value]);
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); onSend(); }
  };
  return (
    <div className="border-t border-knight-border bg-knight-surface/50 backdrop-blur p-4">
      <div className="max-w-3xl mx-auto">
        <div className="flex items-end gap-2 bg-knight-surface border border-knight-border rounded-2xl p-2">
          <button className="p-2 hover:bg-knight-border rounded-xl transition-colors text-knight-muted hover:text-knight-text">
            <Paperclip className="w-5 h-5" />
          </button>
          <textarea
            ref={textareaRef}
            value={value}
            onChange={(e) => onChange(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Message Knight..."
            rows={1}
            className="flex-1 bg-transparent resize-none outline-none text-knight-text placeholder:text-knight-muted py-2 max-h-[200px]"
          />
          <button
            onClick={isListening ? onStopListening : onVoiceToggle}
            className={`p-2 rounded-xl transition-all ${isVoiceMode || isListening ? 'bg-knight-orange text-white shadow-lg shadow-knight-orange/30' : 'hover:bg-knight-border text-knight-muted hover:text-knight-text'}`}
          >
            {isListening ? <MicOff className="w-5 h-5" /> : <Mic className="w-5 h-5" />}
          </button>
          <button
            onClick={onSend}
            disabled={!value.trim() || isLoading}
            className="p-2 bg-gradient-to-r from-knight-cyan to-knight-purple rounded-xl transition-all disabled:opacity-50 disabled:cursor-not-allowed hover:shadow-lg hover:shadow-knight-cyan/20"
          >
            <Send className="w-5 h-5" />
          </button>
        </div>
        <p className="text-center text-xs text-knight-muted mt-2">Press Enter to send · Shift+Enter for new line · Ctrl+V for voice</p>
      </div>
    </div>
  );
}
'@ | Set-Content "$BaseDir\InputBar.tsx" -Encoding UTF8
Write-Host "✓ InputBar.tsx" -ForegroundColor Green
# ─── VOICEOVERLAY.TSX ───
@'
'use client';
import { X } from 'lucide-react';
interface Props { isListening: boolean; isSpeaking: boolean; onClose: () => void; onInterrupt: () => void; }
export function VoiceOverlay({ isListening, isSpeaking, onClose, onInterrupt }: Props) {
  return (
    <div className="fixed inset-0 bg-knight-bg/95 backdrop-blur-xl z-50 flex items-center justify-center">
      <button onClick={onClose} className="absolute top-6 right-6 p-3 hover:bg-knight-border rounded-full">
        <X className="w-6 h-6" />
      </button>
      <div className="text-center">
        <div className={`w-32 h-32 mx-auto mb-8 rounded-full flex items-center justify-center ${isSpeaking ? 'bg-gradient-to-br from-knight-purple to-knight-cyan animate-pulse' : isListening ? 'bg-knight-orange animate-pulse' : 'bg-knight-surface border-2 border-knight-border'}`}>
          {isListening ? (
            <div className="flex items-center gap-1">
              {[1,2,3,4,5].map(i => <div key={i} className="voice-bar" style={{animationDelay:`${i*0.1}s`}} />)}
            </div>
          ) : isSpeaking ? (
            <span className="text-4xl font-bold">K</span>
          ) : (
            <span className="text-4xl">🎤</span>
          )}
        </div>
        <h2 className="text-2xl font-semibold mb-2">
          {isListening ? 'Listening...' : isSpeaking ? 'Knight is speaking...' : 'Voice Mode'}
        </h2>
        <p className="text-knight-muted mb-6">
          {isListening ? 'Speak now - I\'m all ears' : isSpeaking ? 'Click anywhere or press Escape to interrupt' : 'Starting voice capture...'}
        </p>
        {isSpeaking && (
          <button onClick={onInterrupt} className="px-6 py-3 bg-red-500/20 text-red-400 rounded-xl hover:bg-red-500/30 transition-colors">
            Interrupt Knight
          </button>
        )}
      </div>
    </div>
  );
}
'@ | Set-Content "$BaseDir\VoiceOverlay.tsx" -Encoding UTF8
Write-Host "✓ VoiceOverlay.tsx" -ForegroundColor Green
# ─── INDEX EXPORTS ───
@'
export { Header } from './Header';
export { Sidebar } from './Sidebar';
export { ChatContainer } from './ChatContainer';
export { ChatMessage } from './ChatMessage';
export { InputBar } from './InputBar';
export { VoiceOverlay } from './VoiceOverlay';
'@ | Set-Content "$BaseDir\index.ts" -Encoding UTF8
Write-Host "✓ index.ts" -ForegroundColor Green
Write-Host "`n═══════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  ✓ PART 2B COMPLETE - All components created" -ForegroundColor Green
Write-Host "═══════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "`nNext: Run setup-knightbot-part2c.ps1 for main page`n"
Read-Host "Press Enter to exit"