'use client';
import { useState, useRef } from 'react';
import { Copy, Check, User, Pencil, Trash2, Bot, Volume2, RefreshCw, GitBranch, CornerUpLeft, X } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Message, useStore } from '@/lib/store';
import { synthesizeSpeech } from '@/lib/api';

// Avatar URLs - local public files
const KNIGHT_AVATAR = '/knight_avatar.jpg';
const USER_AVATAR = '/user_avatar.jpg';

interface Props { message: Message; onResubmit?: (content: string, messageId: string) => void; onBranch?: (messageId: string) => void; }

export function ChatMessage({ message, onResubmit, onBranch }: Props) {
  const { deleteMessage, messages, addMessage, updateMessage } = useStore();
  const [copied, setCopied] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [editContent, setEditContent] = useState(message.content);
  const [isPlaying, setIsPlaying] = useState(false);
  const [isReRolling, setIsReRolling] = useState(false);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const isUser = message.role === 'user';

  // Copy to clipboard
  const copyToClipboard = async (text: string) => {
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  // Text-to-Speech playback
  const playMessage = async () => {
    if (isPlaying) {
      // Stop playback
      if (audioRef.current) {
        audioRef.current.pause();
        audioRef.current = null;
      }
      setIsPlaying(false);
      return;
    }

    setIsPlaying(true);
    try {
      const audioBlob = await synthesizeSpeech(message.content, 0.5);
      const audioUrl = URL.createObjectURL(audioBlob);
      const audio = new Audio(audioUrl);
      audioRef.current = audio;
      
      audio.onended = () => {
        setIsPlaying(false);
        URL.revokeObjectURL(audioUrl);
      };
      
      audio.onerror = () => {
        setIsPlaying(false);
        URL.revokeObjectURL(audioUrl);
      };
      
      await audio.play();
    } catch (e) {
      console.error('Playback failed:', e);
      setIsPlaying(false);
    }
  };

  // Re-roll: regenerate this response
  const handleReRoll = async () => {
    if (isReRolling || message.role !== 'assistant') return;
    
    setIsReRolling(true);
    
    // Find the previous user message
    const messageIndex = messages.findIndex(m => m.id === message.id);
    const previousUserMessage = messages.slice(0, messageIndex).reverse().find(m => m.role === 'user');
    
    if (previousUserMessage && onResubmit) {
      // Delete current assistant message
      deleteMessage(message.id);
      // Trigger resubmit with the previous user content
      await onResubmit(previousUserMessage.content, previousUserMessage.id);
    }
    
    setIsReRolling(false);
  };

  // Branch: create a new conversation branch from this point
  const handleBranch = () => {
    if (onBranch) {
      onBranch(message.id);
    }
  };

  // Resubmit: edit and resend this message
  const handleResubmit = async () => {
    if (!editContent.trim()) return;
    
    // Update the message content
    updateMessage(message.id, { content: editContent });
    setIsEditing(false);
    
    // Find this message index and delete all subsequent messages
    const messageIndex = messages.findIndex(m => m.id === message.id);
    const messagesToDelete = messages.slice(messageIndex + 1);
    messagesToDelete.forEach(m => deleteMessage(m.id));
    
    // Trigger resubmit
    if (onResubmit) {
      await onResubmit(editContent, message.id);
    }
  };

  return (
    <div className={`flex gap-3 max-w-3xl mx-auto ${isUser ? 'flex-row-reverse' : ''}`}>
      <div className={`w-10 h-10 rounded-full flex items-center justify-center flex-shrink-0 overflow-hidden bg-knight-surface border border-knight-border`}>
        {isUser ? (
          <img 
            src={USER_AVATAR} 
            alt="User" 
            className="w-full h-full object-cover"
            onError={(e) => {
              e.currentTarget.style.display = 'none';
              const fallback = e.currentTarget.parentElement?.querySelector('.user-fallback');
              if (fallback) fallback.classList.remove('hidden');
            }}
          />
        ) : (
          <img 
            src={KNIGHT_AVATAR} 
            alt="Knight" 
            className="w-full h-full object-cover"
            onError={(e) => {
              e.currentTarget.style.display = 'none';
              const fallback = e.currentTarget.parentElement?.querySelector('.knight-fallback');
              if (fallback) fallback.classList.remove('hidden');
            }}
          />
        )}
        <User className="w-5 h-5 user-fallback hidden absolute text-knight-muted" />
        <Bot className="w-5 h-5 knight-fallback hidden absolute text-knight-cyan" />
      </div>
      
      <div className={`group relative max-w-[80%] ${isUser ? 'bg-knight-purple/20 rounded-2xl rounded-tr-md' : 'bg-knight-surface rounded-2xl rounded-tl-md'} px-4 py-3 ${message.isError ? 'border border-red-500/50' : ''}`}>
        {/* Display images for user messages */}
        {isUser && message.images && message.images.length > 0 && (
          <div className="mb-3 flex flex-wrap gap-2">
            {message.images.map((img, idx) => (
              <img 
                key={idx}
                src={img} 
                alt={`Uploaded ${idx + 1}`}
                className="max-w-[200px] max-h-[200px] rounded-lg object-cover border border-knight-border hover:border-knight-cyan/50 transition-colors cursor-pointer"
                onClick={() => window.open(img, '_blank')}
              />
            ))}
          </div>
        )}
        
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
              <button onClick={() => setIsEditing(false)} className="text-xs text-knight-muted hover:text-white px-2 py-1">Cancel</button>
              <button onClick={() => { setIsEditing(false); }} className="text-xs bg-knight-border/50 text-knight-text px-2 py-1 rounded hover:bg-knight-border">Save Only</button>
              <button onClick={handleResubmit} className="text-xs bg-knight-cyan/20 text-knight-cyan px-2 py-1 rounded hover:bg-knight-cyan/30 flex items-center gap-1">
                <CornerUpLeft className="w-3 h-3" /> Resubmit
              </button>
            </div>
          </div>
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
        
        {/* Action Buttons for Assistant Messages */}
        {!isUser && !message.isStreaming && (
          <div className="opacity-0 group-hover:opacity-100 transition-opacity absolute -bottom-10 left-0 flex gap-1 flex-wrap">
            {/* Playback */}
            <button 
              onClick={playMessage} 
              className={`p-1.5 bg-knight-surface border border-knight-border rounded hover:border-knight-cyan/50 ${isPlaying ? 'text-knight-cyan' : ''}`} 
              title={isPlaying ? 'Stop' : 'Play'}
            >
              {isPlaying ? <X className="w-3 h-3" /> : <Volume2 className="w-3 h-3" />}
            </button>
            
            {/* Copy */}
            <button 
              onClick={() => copyToClipboard(message.content)} 
              className="p-1.5 bg-knight-surface border border-knight-border rounded hover:border-knight-cyan/50" 
              title="Copy"
            >
              {copied ? <Check className="w-3 h-3 text-green-400" /> : <Copy className="w-3 h-3" />}
            </button>
            
            {/* Edit */}
            <button 
              onClick={() => setIsEditing(true)} 
              className="p-1.5 bg-knight-surface border border-knight-border rounded hover:border-knight-cyan/50" 
              title="Edit"
            >
              <Pencil className="w-3 h-3" />
            </button>
            
            {/* Re-roll */}
            <button 
              onClick={handleReRoll} 
              disabled={isReRolling}
              className="p-1.5 bg-knight-surface border border-knight-border rounded hover:border-knight-cyan/50 disabled:opacity-50" 
              title="Re-roll Response"
            >
              <RefreshCw className={`w-3 h-3 ${isReRolling ? 'animate-spin' : ''}`} />
            </button>
            
            {/* Branch */}
            <button 
              onClick={handleBranch} 
              className="p-1.5 bg-knight-surface border border-knight-border rounded hover:border-knight-cyan/50" 
              title="Branch Conversation"
            >
              <GitBranch className="w-3 h-3" />
            </button>
            
            {/* Delete */}
            <button 
              onClick={() => deleteMessage(message.id)} 
              className="p-1.5 bg-knight-surface border border-knight-border rounded hover:border-red-500/50" 
              title="Delete"
            >
              <Trash2 className="w-3 h-3 text-knight-muted hover:text-red-400" />
            </button>
          </div>
        )}
        
        {/* Action Buttons for User Messages */}
        {isUser && !isEditing && (
          <div className="opacity-0 group-hover:opacity-100 transition-opacity absolute -bottom-8 right-0 flex gap-1">
            {/* Edit/Resubmit */}
            <button 
              onClick={() => setIsEditing(true)} 
              className="p-1.5 bg-knight-surface border border-knight-border rounded hover:border-knight-cyan/50" 
              title="Edit & Resubmit"
            >
              <Pencil className="w-3 h-3" />
            </button>
            
            {/* Delete */}
            <button 
              onClick={() => deleteMessage(message.id)} 
              className="p-1.5 bg-knight-surface border border-knight-border rounded hover:border-red-500/50" 
              title="Delete"
            >
              <Trash2 className="w-3 h-3 text-knight-muted hover:text-red-400" />
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
