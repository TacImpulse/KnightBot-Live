'use client';

import { LiveKitRoom, RoomAudioRenderer, useLocalParticipant, useVoiceAssistant, BarVisualizer, useRoomContext } from "@livekit/components-react";
import { useCallback, useEffect, useState, useRef } from "react";
import "@livekit/components-styles";
import { X, Mic, MicOff, Settings, Upload, Activity, Maximize2, Minimize2, GripHorizontal, Trash2, Check, User, ImageIcon, Edit2 } from "lucide-react";
import { getLiveKitToken, uploadVoice, getVoices, deleteVoice, uploadAvatar, renameVoice } from "@/lib/api";
import { useStore } from "@/lib/store";
import { RoomEvent } from "livekit-client";

interface Props {
  onClose: () => void;
}

export default function LiveKitAudio({ onClose }: Props) {
  const [token, setToken] = useState("");
  const [url, setUrl] = useState("");
  const [isMinimized, setIsMinimized] = useState(false);

  useEffect(() => {
    // Set initial position
    setPosition({ x: 16, y: 16 });
    (async () => {
      try {
        const data = await getLiveKitToken("knight-room", "user-" + Math.floor(Math.random() * 1000));
        setToken(data.token);
        setUrl(data.url);
      } catch (e) {
        console.error("Failed to get token", e);
      }
    })();
  }, []);

  if (!token || !url) {
    return (
      <div className="fixed bottom-4 right-4 bg-knight-surface border border-knight-border rounded-xl p-4 shadow-lg z-50 flex items-center gap-3">
        <Activity className="w-5 h-5 text-knight-cyan animate-spin" />
        <div className="text-knight-text text-sm">Initializing Neural Link...</div>
      </div>
    );
  }

  return (
    <div 
      ref={containerRef}
      onMouseDown={handleMouseDown}
      style={{ right: `${position.x}px`, bottom: `${position.y}px` }}
      className={`fixed z-50 transition-all duration-300 ease-in-out shadow-2xl border border-knight-border/50 backdrop-blur-md bg-knight-bg/80
      ${isMinimized 
        ? 'w-64 h-16 rounded-full' 
        : 'w-80 h-[400px] rounded-2xl'
      }`}>
      
      <div className="absolute top-2 left-1/2 -translate-x-1/2 z-[60] cursor-move drag-handle group">
        <div className="p-1 rounded-full bg-knight-border/30 group-hover:bg-knight-border/60 transition-colors">
          <GripHorizontal className="w-4 h-4 text-knight-muted group-hover:text-white" />
        </div>
      </div>

      <div className="absolute top-2 right-2 flex gap-2 z-[60]">
        <button 
          onClick={() => setIsMinimized(!isMinimized)} 
          className="p-2 hover:bg-knight-border/50 rounded-full text-knight-muted hover:text-white transition-colors"
        >
          {isMinimized ? <Maximize2 className="w-4 h-4" /> : <Minimize2 className="w-4 h-4" />}
        </button>
        <button 
          onClick={onClose} 
          className="p-2 hover:bg-red-500/20 rounded-full text-knight-muted hover:text-red-400 transition-colors"
        >
          <X className="w-4 h-4" />
        </button>
      </div>
      
      <LiveKitRoom
        token={token}
        serverUrl={url}
        connect={true}
        audio={true}
        video={false}
        className="flex flex-col w-full h-full overflow-hidden"
      >
        <ChatSyncHandler />
        {isMinimized ? <MinimizedState /> : <VisualizerState />}
        <RoomAudioRenderer />
      </LiveKitRoom>
    </div>
  );
}

function ChatSyncHandler() {
  const room = useRoomContext();
  const { addMessage } = useStore();
  const processedMessages = useRef(new Set<string>());

  useEffect(() => {
    const handleData = (payload: Uint8Array, participant: any, kind: any) => {
      try {
        const str = new TextDecoder().decode(payload);
        const data = JSON.parse(str);
        
        if (data.type === 'chat') {
           // Prevent duplicate messages if any (simple timestamp check)
           const key = `${data.timestamp}-${data.content}`;
           if (processedMessages.current.has(key)) return;
           processedMessages.current.add(key);

           // Keep set size manageable
           if (processedMessages.current.size > 100) {
             const it = processedMessages.current.values();
             processedMessages.current.delete(it.next().value);
           }

           addMessage({
             id: Date.now().toString(),
             role: data.role,
             content: data.content,
             timestamp: new Date()
           });
        }
      } catch (e) {
        console.error("Failed to parse data packet", e);
      }
    };

    room.on(RoomEvent.DataReceived, handleData);
    return () => { room.off(RoomEvent.DataReceived, handleData); };
  }, [room, addMessage]);

  return null;
}

function MinimizedState() {
  const { state } = useVoiceAssistant();
  
  return (
    <div className="flex items-center gap-4 px-4 h-full">
      <div className={`w-3 h-3 rounded-full animate-pulse ${state === 'speaking' ? 'bg-knight-cyan' : 'bg-knight-orange'}`} />
      <span className="text-sm font-medium text-white truncate">
        {state === 'speaking' ? 'Knight is speaking...' : 'Listening...'}
      </span>
    </div>
  );
}

function VisualizerState() {
  const { state, audioTrack } = useVoiceAssistant();
  const { isMicrophoneEnabled, localParticipant } = useLocalParticipant();
  const [showSettings, setShowSettings] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const avatarInputRef = useRef<HTMLInputElement>(null);
  const [voices, setVoices] = useState<string[]>([]);
  const [selectedVoice, setSelectedVoice] = useState<string | null>(null);
  const [editingVoice, setEditingVoice] = useState<string | null>(null);
  const [editName, setEditName] = useState("");
  const [avatarUploadVoice, setAvatarUploadVoice] = useState<string | null>(null);
  
  useEffect(() => {
    if (showSettings) {
      loadVoices();
    }
  }, [showSettings]);

  const loadVoices = async () => {
    const v = await getVoices();
    setVoices(v.voices);
    setSelectedVoice(v.default);
  };

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files?.[0]) {
      try {
        const file = e.target.files[0];
        const name = prompt("Name this voice profile:", file.name.replace('.wav', ''));
        if (!name) return;
        
        await uploadVoice(file, name);
        await loadVoices();
        alert("Voice uploaded! Restarting Knight's vocal cords...");
      } catch (err) {
        alert("Failed to upload voice");
      }
    }
  };

  const handleAvatarUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files?.[0] && avatarUploadVoice) {
      try {
        await uploadAvatar(avatarUploadVoice, e.target.files[0]);
        // Force refresh of image by appending timestamp or just reload list (though list doesn't have image url, component constructs it)
        // We'll just force a re-render or let the user see it on next load. 
        // A simple way to refresh the image is to update a key or state, but since we use direct URL, browser caching might be an issue.
        // We can append ?t=Date.now() to the image src.
        setAvatarUploadVoice(null);
        await loadVoices(); // Refresh list
      } catch (err) {
        alert("Failed to upload avatar");
      }
    }
  };

  const handleRename = async (voice: string) => {
    if (!editName.trim() || editName === voice) {
      setEditingVoice(null);
      return;
    }
    try {
      await renameVoice(voice, editName);
      await loadVoices();
      setEditingVoice(null);
    } catch (err) {
      alert("Failed to rename voice");
    }
  };

  const startEditing = (voice: string) => {
    setEditingVoice(voice);
    setEditName(voice);
  };

  const handleDelete = async (voice: string) => {
    if (confirm(`Delete voice profile '${voice}'?`)) {
      try {
        await deleteVoice(voice);
        await loadVoices();
      } catch (err) {
        alert("Failed to delete voice");
      }
    }
  };

  const triggerAvatarUpload = (voice: string) => {
    setAvatarUploadVoice(voice);
    avatarInputRef.current?.click();
  };

  if (showSettings) {
    return (
      <div className="flex flex-col h-full p-6">
        <div className="flex justify-between items-center mb-6">
          <h3 className="text-xl font-bold text-white">Voice Settings</h3>
          <button onClick={() => setShowSettings(false)} className="text-knight-muted hover:text-white">Back</button>
        </div>
        
        <input 
          type="file" 
          accept="image/*" 
          ref={avatarInputRef} 
          className="hidden" 
          onChange={handleAvatarUpload}
        />

        <div className="space-y-6 overflow-y-auto pr-2 flex-1">
          {/* Upload Section */}
          <div className="bg-knight-surface p-4 rounded-lg border border-knight-border">
            <h4 className="text-sm font-medium text-knight-muted mb-3">Cloning Lab</h4>
            <p className="text-xs text-knight-muted mb-4">Upload a 10-20s clean WAV file to clone a new voice.</p>
            
            <input 
              type="file" 
              accept=".wav" 
              ref={fileInputRef} 
              className="hidden" 
              onChange={handleUpload}
            />
            
            <button 
              onClick={() => fileInputRef.current?.click()}
              className="flex items-center justify-center gap-2 w-full py-3 bg-knight-border hover:bg-knight-purple/20 border border-knight-border rounded-lg transition-all"
            >
              <Upload className="w-4 h-4" />
              <span>Upload Voice Sample</span>
            </button>
          </div>

          {/* Voice Profiles */}
          <div className="bg-knight-surface p-4 rounded-lg border border-knight-border">
            <h4 className="text-sm font-medium text-knight-muted mb-3">Voice Profiles</h4>
            <div className="space-y-3">
              {voices.map(voice => (
                <div key={voice} className="flex items-center justify-between p-3 rounded bg-knight-bg/50 border border-knight-border/30 hover:border-knight-cyan/30 transition-all group">
                  <div className="flex items-center gap-3 flex-1">
                    {/* Avatar */}
                    <div className="relative w-10 h-10 shrink-0">
                       <img 
                         src={`/api/tts/voices/${voice}/avatar?t=${Date.now()}`} 
                         alt={voice}
                         className="w-full h-full rounded-full object-cover bg-knight-surface border border-knight-border"
                         onError={(e) => {
                           (e.target as HTMLImageElement).src = 'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="gray" stroke-width="2"><circle cx="12" cy="8" r="4"/><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/></svg>';
                         }}
                       />
                       <button 
                         onClick={() => triggerAvatarUpload(voice)}
                         className="absolute -bottom-1 -right-1 p-1 bg-knight-surface rounded-full border border-knight-border hover:border-knight-cyan text-knight-muted hover:text-knight-cyan opacity-0 group-hover:opacity-100 transition-opacity"
                       >
                         <ImageIcon className="w-3 h-3" />
                       </button>
                    </div>

                    {/* Name / Edit Input */}
                    {editingVoice === voice ? (
                      <div className="flex items-center gap-2 flex-1">
                        <input 
                          value={editName}
                          onChange={(e) => setEditName(e.target.value)}
                          className="bg-knight-bg border border-knight-cyan text-sm px-2 py-1 rounded w-full outline-none text-white"
                          autoFocus
                          onKeyDown={(e) => e.key === 'Enter' && handleRename(voice)}
                        />
                        <button onClick={() => handleRename(voice)} className="text-green-400 hover:text-green-300"><Check className="w-4 h-4"/></button>
                        <button onClick={() => setEditingVoice(null)} className="text-red-400 hover:text-red-300"><X className="w-4 h-4"/></button>
                      </div>
                    ) : (
                      <div className="flex flex-col">
                        <span className={`text-sm font-medium ${voice === selectedVoice ? 'text-knight-cyan' : 'text-white'}`}>
                          {voice} {voice === selectedVoice && '(Active)'}
                        </span>
                      </div>
                    )}
                  </div>

                  {/* Actions */}
                   {editingVoice !== voice && (
                     <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity ml-2">
                       {voice !== selectedVoice && (
                         <button 
                           onClick={() => handleSelect(voice)}
                           className="p-1.5 hover:bg-knight-cyan/20 rounded text-knight-muted hover:text-knight-cyan"
                           title="Select Active Voice"
                         >
                           <PlayCircle className="w-3.5 h-3.5" />
                         </button>
                       )}
                       <button 
                         onClick={() => startEditing(voice)}
                         className="p-1.5 hover:bg-knight-border/50 rounded text-knight-muted hover:text-white"
                         title="Rename"
                       >
                         <Edit2 className="w-3.5 h-3.5" />
                       </button>
                       <button 
                         onClick={() => handleDelete(voice)}
                         className="p-1.5 hover:bg-red-500/20 rounded text-knight-muted hover:text-red-400"
                         title="Delete"
                       >
                         <Trash2 className="w-3.5 h-3.5" />
                       </button>
                     </div>
                   )}
                </div>
              ))}
              {voices.length === 0 && (
                <p className="text-xs text-knight-muted italic text-center py-2">No custom voices found</p>
              )}
            </div>
          </div>
        </div>
      </div>
    );
  }
  
  return (
    <div className="flex flex-col items-center justify-center h-full gap-8 p-6 relative">
      <div className="absolute top-4 left-4">
        <button 
          onClick={() => setShowSettings(true)}
          className="p-2 hover:bg-knight-border rounded-full text-knight-muted hover:text-white transition-colors"
        >
          <Settings className="w-5 h-5" />
        </button>
      </div>

      <div className={`relative w-40 h-40 flex items-center justify-center transition-all duration-500`}>
        {/* Glow Effects */}
        <div className={`absolute inset-0 rounded-full blur-2xl transition-opacity duration-500
          ${state === 'speaking' ? 'bg-knight-cyan/40 opacity-100' : 'bg-knight-purple/20 opacity-50'}`} 
        />
        
        <div className={`relative w-full h-full rounded-full flex items-center justify-center border-2 transition-all duration-300
          ${state === 'speaking' ? 'border-knight-cyan bg-knight-surface/50' : 'border-knight-border bg-knight-surface'}`}>
          
          {state === 'speaking' ? (
             <div className="flex items-center gap-1 h-12">
               {[1,2,3,4,5].map(i => (
                 <div key={i} className="w-1.5 bg-knight-cyan rounded-full animate-voice-bar" 
                      style={{ animationDelay: `${i * 0.1}s`, height: '40%' }} />
               ))}
             </div>
          ) : (
             <BarVisualizer
               state={state}
               barCount={5}
               trackRef={audioTrack}
               className="h-16 gap-1.5"
               options={{ minHeight: 10, maxHeight: 60 }}
             />
          )}
        </div>
      </div>

      <div className="text-center space-y-1">
        <h2 className="text-2xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-white to-gray-400">
          {state === 'speaking' ? 'Speaking...' : 
           state === 'listening' ? 'Listening...' : 
           state === 'thinking' ? 'Thinking...' : 
           'Connected'}
        </h2>
        <p className="text-knight-muted text-sm">
          {state === 'listening' ? 'Go ahead...' : 'Neural Link Active'}
        </p>
      </div>

      <button 
        onClick={() => localParticipant.setMicrophoneEnabled(!isMicrophoneEnabled)}
        className={`p-4 rounded-full transition-all duration-300 transform hover:scale-105
          ${isMicrophoneEnabled 
            ? 'bg-knight-surface border border-knight-cyan/30 text-knight-cyan shadow-[0_0_20px_rgba(34,211,238,0.2)]' 
            : 'bg-red-500/10 border border-red-500/30 text-red-400'}`}
      >
        {isMicrophoneEnabled ? <Mic className="w-6 h-6" /> : <MicOff className="w-6 h-6" />}
      </button>
    </div>
  );
}
