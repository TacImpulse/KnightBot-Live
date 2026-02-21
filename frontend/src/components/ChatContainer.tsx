'use client';
import { useRef, useEffect } from 'react';
import { Message } from '@/lib/store';
import { ChatMessage } from './ChatMessage';
interface Props { 
  messages: Message[]; 
  isLoading: boolean; 
  onSuggestionClick: (text: string) => void; 
  onResubmit?: (content: string, messageId: string) => void;
  onBranch?: (messageId: string) => void;
}
export function ChatContainer({ messages, isLoading, onSuggestionClick, onResubmit, onBranch }: Props) {
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
              <button 
                key={s} 
                onClick={() => onSuggestionClick(s)}
                className="px-4 py-2 bg-knight-surface border border-knight-border rounded-full text-sm hover:border-knight-cyan/50 transition-colors"
              >
                {s}
              </button>
            ))}
          </div>
        </div>
      </div>
    );
  }
  return (
    <div className="flex-1 overflow-y-auto p-4 space-y-6 pb-20">
      {messages.map(m => (
        <ChatMessage 
          key={m.id} 
          message={m} 
          onResubmit={onResubmit}
          onBranch={onBranch}
        />
      ))}
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
