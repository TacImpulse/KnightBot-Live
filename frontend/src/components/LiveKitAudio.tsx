'use client';

import { LiveKitRoom, RoomAudioRenderer, useLocalParticipant, useVoiceAssistant, BarVisualizer, useRoomContext } from "@livekit/components-react";
import { useEffect, useState, useRef } from "react";
import "@livekit/components-styles";
import { X, Mic, MicOff, Settings, Activity, Maximize2, Minimize2, GripHorizontal } from "lucide-react";
import { getLiveKitToken } from "@/lib/api";
import { useStore } from "@/lib/store";
import { RoomEvent } from "livekit-client";

interface Props {
  onClose: () => void;
}

export default function LiveKitAudio({ onClose }: Props) {
  const [token, setToken] = useState("");
  const [url, setUrl] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isMinimized, setIsMinimized] = useState(false);
  const [position, setPosition] = useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);
  const [dragOffset, setDragOffset] = useState({ x: 0, y: 0 });
  const containerRef = useRef<HTMLDivElement>(null);
  const { setSettingsOpen } = useStore();

  const handleMouseDown = (e: React.MouseEvent) => {
    if (containerRef.current && (e.target as HTMLElement).closest('.drag-handle')) {
      setIsDragging(true);
      const rect = containerRef.current.getBoundingClientRect();
      setDragOffset({ x: e.clientX - rect.left, y: e.clientY - rect.top });
    }
  };

  const handleMouseMove = (e: MouseEvent) => {
    if (isDragging) {
      const x = window.innerWidth - e.clientX + dragOffset.x - (containerRef.current?.offsetWidth || 0);
      const y = window.innerHeight - e.clientY + dragOffset.y - (containerRef.current?.offsetHeight || 0);
      setPosition({ x, y });
    }
  };

  const handleMouseUp = () => setIsDragging(false);

  useEffect(() => {
    if (isDragging) {
      window.addEventListener('mousemove', handleMouseMove);
      window.addEventListener('mouseup', handleMouseUp);
    }
    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isDragging]);

  useEffect(() => {
    // Set initial position
    setPosition({ x: 16, y: 16 });

    let cancelled = false;
    let retryCount = 0;
    const maxRetries = 3;
    let retryTimer: ReturnType<typeof setTimeout> | null = null;

    const connect = async () => {
      try {
        if (cancelled) return;
        setIsLoading(true);
        setError(null);

        const data = await getLiveKitToken(
          "knight-room",
          "user-" + Math.floor(Math.random() * 1000)
        );

        if (!data?.token || !data?.url) {
          throw new Error("Invalid token response from server");
        }
        if (cancelled) return;

        setToken(data.token);
        setUrl(data.url);
        setIsLoading(false);
      } catch (e: any) {
        if (cancelled) return;
        console.error("Failed to get token", e);

        if (retryCount < maxRetries) {
          retryCount++;
          console.log(`Retrying connection (${retryCount}/${maxRetries})...`);
          retryTimer = setTimeout(connect, 2000); // Retry after 2s
        } else {
          setError(e?.message || "Failed to initialize voice connection");
          setIsLoading(false);
        }
      }
    };

    connect();

    return () => {
      cancelled = true;
      if (retryTimer) clearTimeout(retryTimer);
    };
  }, []);

  if (isLoading) {
    return (
      <div className="fixed bottom-4 right-4 bg-knight-surface border border-knight-border rounded-xl p-4 shadow-lg z-50 flex items-center gap-3">
        <Activity className="w-5 h-5 text-knight-cyan animate-spin" />
        <div className="text-knight-text text-sm">Initializing Neural Link...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="fixed bottom-4 right-4 bg-red-900/30 border border-red-500/50 rounded-xl p-4 shadow-lg z-50 flex flex-col gap-2 max-w-xs">
        <div className="flex items-center gap-2 text-red-400 font-semibold">
          <X className="w-5 h-5" />
          <span>Neural Link Failed</span>
        </div>
        <div className="text-red-200/80 text-sm">{error}</div>
        <button
          onClick={onClose}
          className="mt-1 px-3 py-1 bg-red-500/20 hover:bg-red-500/30 text-red-300 rounded-lg text-sm transition-colors"
        >
          Close
        </button>
      </div>
    );
  }

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

        // Be defensive: LiveKit data packets may include non-chat payloads.
        if (!data || typeof data !== 'object') return;
        if ((data as any).type !== 'chat') return;

        {
          // Prevent duplicate messages if any (simple timestamp check)
          const key = `${(data as any).timestamp}-${(data as any).content}`;
          if (processedMessages.current.has(key)) return;
          processedMessages.current.add(key);

          // Keep set size manageable
          if (processedMessages.current.size > 100) {
            const it = processedMessages.current.values();
            processedMessages.current.delete(it.next().value);
          }

          addMessage({
            id: Date.now().toString(),
            role: (data as any).role,
            content: (data as any).content,
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
  const { setSettingsOpen } = useStore();

  return (
    <div className="flex flex-col items-center justify-center h-full gap-8 p-6 relative">
      <div className="absolute top-4 left-4">
        <button
          onClick={() => setSettingsOpen(true)}
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
              {[1, 2, 3, 4, 5].map(i => (
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
