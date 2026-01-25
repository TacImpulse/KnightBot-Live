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
  const [isEditing, setIsEditing] = useState(false);
  const [editContent, setEditContent] = useState(message.content);

  const handleSave = () => {
    // TODO: Update message in store
    setIsEditing(false);
  };

  return (
    <div className={`flex gap-3 max-w-3xl mx-auto ${isUser ? 'flex-row-reverse' : ''}`}>
      <div className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 ${isUser ? 'bg-knight-purple' : 'bg-gradient-to-br from-knight-cyan to-knight-purple'}`}>
        {isUser ? <User className="w-4 h-4" /> : <span className="text-sm font-bold">K</span>}
      </div>
      <div className={`group relative max-w-[80%] ${isUser ? 'bg-knight-purple/20 rounded-2xl rounded-tr-md' : 'bg-knight-surface rounded-2xl rounded-tl-md'} px-4 py-3 ${message.isError ? 'border border-red-500/50' : ''}`}>
        {message.isStreaming ? (
          <span className="text-knight-text">{message.content}<span className="animate-pulse">▊</span></span>
        ) : isEditing ? (
          <div className="flex flex-col gap-2 min-w-[300px]">
            <textarea 
              value={editContent} 
              onChange={(e) => setEditContent(e.target.value)}
              className="w-full bg-knight-bg/50 border border-knight-border rounded p-2 text-knight-text outline-none focus:border-knight-cyan"
              rows={3}
            />
            <div className="flex justify-end gap-2">
              <button onClick={() => setIsEditing(false)} className="text-xs text-knight-muted hover:text-white">Cancel</button>
              <button onClick={handleSave} className="text-xs bg-knight-cyan/20 text-knight-cyan px-2 py-1 rounded hover:bg-knight-cyan/30">Save</button>
            </div>
          </div>
        ) : isUser ? (
          <p className="text-knight-text whitespace-pre-wrap">{editContent || message.content}</p>
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
            <button onClick={() => setIsEditing(true)} className="p-1.5 bg-knight-surface border border-knight-border rounded hover:border-knight-cyan/50">
              <Pencil className="w-3 h-3 text-knight-muted hover:text-knight-cyan" />
            </button>
            <button onClick={() => copyToClipboard(message.content)} className="p-1.5 bg-knight-surface border border-knight-border rounded hover:border-knight-cyan/50">
              {copied ? <Check className="w-3 h-3 text-green-400" /> : <Copy className="w-3 h-3" />}
            </button>
          </div>
        )}
        {isUser && !isEditing && (
          <div className="opacity-0 group-hover:opacity-100 transition-opacity absolute -bottom-8 right-0 flex gap-1">
            <button onClick={() => setIsEditing(true)} className="p-1.5 bg-knight-surface border border-knight-border rounded hover:border-knight-cyan/50">
              <Pencil className="w-3 h-3 text-knight-muted hover:text-knight-cyan" />
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
