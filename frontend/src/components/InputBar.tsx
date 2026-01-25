'use client';
import { useRef, useEffect } from 'react';
import { Send, Mic, MicOff, Paperclip, X } from 'lucide-react';

interface Props {
  value: string; onChange: (v: string) => void; onSend: () => void;
  onVoiceToggle: () => void; isVoiceMode: boolean; isListening: boolean;
  isLoading: boolean; onStopListening: () => void;
  selectedFile: File | null; onFileSelect: (f: File | null) => void;
}
export function InputBar({ value, onChange, onSend, onVoiceToggle, isVoiceMode, isListening, isLoading, onStopListening, selectedFile, onFileSelect }: Props) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = Math.min(textareaRef.current.scrollHeight, 200) + 'px';
    }
  }, [value]);
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); onSend(); }
  };
  const handleFileClick = () => {
    fileInputRef.current?.click();
  };
  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files?.[0]) {
      onFileSelect(e.target.files[0]);
    }
  };
  const clearFile = () => {
    onFileSelect(null);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };
  const handlePaste = (e: React.ClipboardEvent) => {
    if (e.clipboardData.files.length > 0) {
      onFileSelect(e.clipboardData.files[0]);
    }
  };
  return (
    <div className="border-t border-knight-border bg-knight-surface/50 backdrop-blur p-4">
      <div className="max-w-3xl mx-auto">
        {selectedFile && (
          <div className="mb-2 flex items-center gap-2 bg-knight-surface border border-knight-border rounded-lg px-3 py-2 w-fit">
            <span className="text-sm text-knight-text truncate max-w-[200px]">{selectedFile.name}</span>
            <button onClick={clearFile} className="p-1 hover:bg-knight-border rounded-full text-knight-muted hover:text-red-400">
              <X className="w-3 h-3" />
            </button>
          </div>
        )}
        <div className="flex items-end gap-2 bg-knight-surface border border-knight-border rounded-2xl p-2">
          <input
             type="file"
             ref={fileInputRef}
             className="hidden"
             onChange={handleFileChange}
             accept="image/*"
          />
          <button 
            onClick={handleFileClick}
            className={`p-2 hover:bg-knight-border rounded-xl transition-colors ${selectedFile ? 'text-knight-cyan' : 'text-knight-muted hover:text-knight-text'}`}
          >
            <Paperclip className="w-5 h-5" />
          </button>
          <textarea
            ref={textareaRef}
            value={value}
            onChange={(e) => onChange(e.target.value)}
            onKeyDown={handleKeyDown}
            onPaste={handlePaste}
            placeholder={isListening ? "Listening..." : "Message Knight..."}
            className="flex-1 bg-transparent border-none outline-none resize-none py-3 px-2 text-knight-text placeholder-knight-muted max-h-[200px]"
            rows={1}
            disabled={isLoading || isVoiceMode}
          />
          <button
            onClick={isListening ? onStopListening : onVoiceToggle}
            className={`p-2 rounded-xl transition-all ${isVoiceMode || isListening ? 'bg-knight-orange text-white shadow-lg shadow-knight-orange/30' : 'hover:bg-knight-border text-knight-muted hover:text-knight-text'}`}
          >
            {isListening ? <MicOff className="w-5 h-5" /> : <Mic className="w-5 h-5" />}
          </button>
          <button
            onClick={onSend}
            disabled={(!value.trim() && !selectedFile) || isLoading}
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
