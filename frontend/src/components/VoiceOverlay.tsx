'use client';
import { X } from 'lucide-react';
interface Props { isListening: boolean; isSpeaking: boolean; onClose: () => void; onInterrupt: () => void; }
export function VoiceOverlay({ isListening, isSpeaking, onClose, onInterrupt }: Props) {
  return (
    <div className="fixed inset-0 bg-knight-bg/95 backdrop-blur-xl z-50 flex items-center justify-center">
      <button onClick={onClose} className="absolute top-6 right-6 p-3 hover:bg-knight-border rounded-full">
        <X className="w-6 h-6" />
      </button>
      <div className="text-center relative">
        <div className={`w-32 h-32 mx-auto mb-8 rounded-full flex items-center justify-center transition-all duration-300 ${isSpeaking ? 'bg-gradient-to-br from-knight-purple to-knight-cyan animate-pulse shadow-[0_0_50px_rgba(139,92,246,0.5)]' : isListening ? 'bg-knight-orange animate-pulse shadow-[0_0_50px_rgba(249,115,22,0.5)]' : 'bg-knight-surface border-2 border-knight-border'}`}>
          {isListening ? (
            <div className="flex items-center gap-1 h-12">
              {[1,2,3,4,5].map(i => <div key={i} className="voice-bar w-1.5 bg-white rounded-full mx-0.5" style={{animation:`voice-bar 1s ease-in-out infinite`, animationDelay:`${i*0.1}s`}} />)}
            </div>
          ) : isSpeaking ? (
            <span className="text-4xl font-bold text-white">K</span>
          ) : (
            <span className="text-4xl">🎤</span>
          )}
        </div>
        
        {isListening && (
           <div className="absolute top-0 left-1/2 -translate-x-1/2 -translate-y-12 whitespace-nowrap">
             <span className="text-sm text-knight-muted animate-fade-in-up">Listening...</span>
           </div>
        )}

        <h2 className="text-2xl font-semibold mb-2 text-knight-text">
          {isListening ? 'I\'m listening...' : isSpeaking ? 'Speaking...' : 'Voice Mode'}
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
