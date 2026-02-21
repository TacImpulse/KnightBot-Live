'use client';

import { useState, useRef, useCallback, useEffect } from 'react';
import { Header } from '@/components/Header';
import { Sidebar } from '@/components/Sidebar';
import { ChatContainer } from '@/components/ChatContainer';
import { InputBar } from '@/components/InputBar';
import LiveKitAudio from '@/components/LiveKitAudio';
import { VoiceSettingsPanel } from '@/components/VoiceSettingsPanel';
import { useStore } from '@/lib/store';
import { sendMessage, synthesizeSpeech, transcribeAudio } from '@/lib/api';
import { toBackendVoiceProfile } from '@/lib/voiceProfiles';

const USE_LIVEKIT_VOICE = process.env.NEXT_PUBLIC_USE_LIVEKIT_VOICE === '1';
const TTS_MAX_CHARS = Number(process.env.NEXT_PUBLIC_TTS_MAX_CHARS || '0');

function toSpeechText(text: string): string {
  const normalized = text.replace(/\s+/g, ' ').trim();
  if (!Number.isFinite(TTS_MAX_CHARS) || TTS_MAX_CHARS <= 0) return normalized;
  if (normalized.length <= TTS_MAX_CHARS) return normalized;

  const clipped = normalized.slice(0, TTS_MAX_CHARS);
  const lastPeriod = clipped.lastIndexOf('. ');
  const naturalCut = lastPeriod > 80 ? clipped.slice(0, lastPeriod + 1) : clipped;
  return `${naturalCut} ...`;
}

export default function Home() {
  const {
    messages, addMessage, updateMessage,
    isVoiceMode, setVoiceMode,
    isListening, setListening,
    isSpeaking, setSpeaking,
    isMuted, currentVoice, systemPrompt,
    voiceResponseMode, setVoiceResponseMode,
    isSettingsOpen, setSettingsOpen
  } = useStore();

  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const isVoiceModeRef = useRef(isVoiceMode);
  const suppressAutoRestartRef = useRef(false);

  useEffect(() => {
    isVoiceModeRef.current = isVoiceMode;
  }, [isVoiceMode]);

  // Send message to Knight
  const handleSend = useCallback(async (text: string) => {
    if ((!text.trim() && !selectedFile) || isLoading) return;

    // Convert file to base64 if present
    let images: string[] | undefined;
    if (selectedFile) {
      try {
        const reader = new FileReader();
        const base64Promise = new Promise<string>((resolve) => {
          reader.onload = (e) => resolve(e.target?.result as string);
        });
        reader.readAsDataURL(selectedFile);
        images = [await base64Promise];
      } catch (e) {
        console.error('File read error:', e);
      }
    }

    const userMsg = {
      id: Date.now().toString(),
      role: 'user' as const,
      content: text,
      timestamp: new Date(),
      images: images || undefined
    };
    addMessage(userMsg);
    setInput('');
    setSelectedFile(null); // Clear file after sending
    setIsLoading(true);

    const assistantId = (Date.now() + 1).toString();
    addMessage({
      id: assistantId,
      role: 'assistant',
      content: '',
      timestamp: new Date(),
      isStreaming: true
    });

    try {
      const response = await sendMessage(
        text,
        currentVoice || undefined,
        systemPrompt || undefined,
        images,
        isVoiceModeRef.current,
        isVoiceModeRef.current ? toBackendVoiceProfile(voiceResponseMode) : undefined
      );
      updateMessage(assistantId, {
        content: response.text,
        isStreaming: false
      });

      // Text-to-speech if not muted (regardless of voice mode)
      if (!isMuted) {
        setSpeaking(true);
        try {
          const speechText = toSpeechText(response.text);
          const audioBlob = await synthesizeSpeech(speechText, 0.5, currentVoice || undefined);
          const audioUrl = URL.createObjectURL(audioBlob);
          const audio = new Audio(audioUrl);
          audioRef.current = audio;

          // Resume listening after speaking finishes (only in local voice mode)
          audio.onended = () => {
            setSpeaking(false);
            URL.revokeObjectURL(audioUrl);
            if (isVoiceModeRef.current && !USE_LIVEKIT_VOICE) {
              setTimeout(() => startListening(), 500);
            }
          };

          audio.onerror = () => {
            setSpeaking(false);
            URL.revokeObjectURL(audioUrl);
          };

          await audio.play();
        } catch (e) {
          console.error('TTS failed:', e);
          setSpeaking(false);
        }
      } else {
        // If muted in local voice mode, resume listening for next turn.
        if (isVoiceModeRef.current && !USE_LIVEKIT_VOICE) {
          setTimeout(() => startListening(), 500);
        }
      }
    } catch (error) {
      console.error('Chat error:', error);
      updateMessage(assistantId, {
        content: '[sigh] Something went wrong. Make sure the backend is running on port 8100.',
        isStreaming: false,
        isError: true
      });
    } finally {
      setIsLoading(false);
    }
  }, [isLoading, isMuted, addMessage, updateMessage, setSpeaking, currentVoice, systemPrompt, selectedFile, voiceResponseMode]);

  // Stop voice recording
  const stopListening = useCallback((suppressRestart: boolean = false) => {
    if (suppressRestart) {
      suppressAutoRestartRef.current = true;
    }
    if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'recording') {
      mediaRecorderRef.current.stop();
    }
  }, []);

  // Start voice recording
  const startListening = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true }
      });

      // VAD State
      let silenceStart = 0;
      let isSpeakingDetected = false;
      let noiseFloor = 0.008;
      let calibrationFrames = 0;
      const START_THRESHOLD_MIN = 0.014;
      const END_THRESHOLD_MIN = 0.009;
      const SILENCE_THRESHOLD = 1800;
      const NO_SPEECH_TIMEOUT = 7000;
      const MAX_RECORDING_MS = 25000;
      const MIN_BLOB_BYTES = 300;
      const recordingStartedAt = Date.now();

      const preferredMimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
        ? 'audio/webm;codecs=opus'
        : (MediaRecorder.isTypeSupported('audio/webm') ? 'audio/webm' : '');
      const mediaRecorder = preferredMimeType
        ? new MediaRecorder(stream, { mimeType: preferredMimeType })
        : new MediaRecorder(stream);

      // Request AudioContext access properly
      const AudioContextClass = window.AudioContext || (window as any).webkitAudioContext;
      const audioContext = new AudioContextClass();
      const source = audioContext.createMediaStreamSource(stream);
      const analyser = audioContext.createAnalyser();
      analyser.fftSize = 2048;
      source.connect(analyser);

      const bufferLength = analyser.frequencyBinCount;
      const dataArray = new Uint8Array(bufferLength);
      mediaRecorderRef.current = mediaRecorder;
      chunksRef.current = [];

      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };

      // VAD Loop
      const checkAudioLevel = () => {
        if (mediaRecorder.state !== 'recording') {
          audioContext.close();
          return;
        }

        if (Date.now() - recordingStartedAt > MAX_RECORDING_MS) {
          stopListening();
          return;
        }

        analyser.getByteTimeDomainData(dataArray);
        let sumSquares = 0;
        for (let i = 0; i < bufferLength; i++) {
          const centered = (dataArray[i] - 128) / 128;
          sumSquares += centered * centered;
        }
        const rms = Math.sqrt(sumSquares / bufferLength);
        const now = Date.now();

        if (!isSpeakingDetected) {
          // Calibrate ambient noise floor for a short initial window.
          if (calibrationFrames < 80) {
            noiseFloor = noiseFloor * 0.9 + rms * 0.1;
            calibrationFrames += 1;
          }

          const startThreshold = Math.max(START_THRESHOLD_MIN, noiseFloor * 2.8);
          if (rms > startThreshold) {
            isSpeakingDetected = true;
            silenceStart = now;
          } else if (now - recordingStartedAt > NO_SPEECH_TIMEOUT) {
            stopListening();
            return;
          }
        } else {
          const endThreshold = Math.max(END_THRESHOLD_MIN, noiseFloor * 1.8);
          if (rms > endThreshold) {
            silenceStart = now;
          } else if (silenceStart > 0 && (now - silenceStart > SILENCE_THRESHOLD)) {
            stopListening();
            return;
          }
        }
        requestAnimationFrame(checkAudioLevel);
      };

      mediaRecorder.onstop = async () => {
        // Close audio context immediately
        if (audioContext.state !== 'closed') {
          audioContext.close();
        }

        const audioBlob = new Blob(chunksRef.current, { type: preferredMimeType || 'audio/webm' });
        stream.getTracks().forEach(t => t.stop());

        // Don't setListening(false) here immediately if we want to keep the "thinking" UI state
        // But for now, we do need to stop the visual indicator
        setListening(false);

        const suppressRestart = suppressAutoRestartRef.current;
        suppressAutoRestartRef.current = false;
        const voiceModeStillOn = isVoiceModeRef.current && !suppressRestart;
        if (audioBlob.size >= MIN_BLOB_BYTES && voiceModeStillOn) {
          try {
            const result = await transcribeAudio(audioBlob);
            if (result.text && result.text.trim() && !result.error) {
              handleSend(result.text);
            } else if (result.error) {
              console.error('STT returned error:', result.error);
              if (voiceModeStillOn) startListening();
            } else {
              if (voiceModeStillOn) startListening();
            }
          } catch (e) {
            console.error('STT failed:', e);
            if (voiceModeStillOn) startListening();
          }
        } else {
          if (voiceModeStillOn) {
            startListening();
          }
        }
      };

      mediaRecorder.start(250);
      setListening(true);
      checkAudioLevel(); // Start VAD loop

    } catch (e) {
      console.error('Microphone access denied:', e);
      alert('Microphone access is required for voice mode. Please allow microphone access and try again.');
    }
  }, [handleSend, setListening, stopListening]);

  // Interrupt Knight (stop audio playback)
  const handleInterrupt = useCallback(() => {
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.currentTime = 0;
      audioRef.current = null;
    }

    setSpeaking(false);
    stopListening(true);

    setListening(false);
  }, [setSpeaking, setListening, stopListening]);

  // Toggle voice mode.
  // Default path is local browser STT for reliability; LiveKit is opt-in.
  const toggleVoiceMode = useCallback(() => {
    if (isVoiceMode) {
      isVoiceModeRef.current = false;
      suppressAutoRestartRef.current = true;
      handleInterrupt();
      setVoiceMode(false);
    } else {
      isVoiceModeRef.current = true;
      suppressAutoRestartRef.current = false;
      setVoiceMode(true);
      if (!USE_LIVEKIT_VOICE) {
        setTimeout(() => startListening(), 150);
      }
    }
  }, [isVoiceMode, handleInterrupt, setVoiceMode, startListening]);

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Escape - interrupt everything
      if (e.key === 'Escape') {
        isVoiceModeRef.current = false;
        suppressAutoRestartRef.current = true;
        handleInterrupt();
        if (isVoiceMode) setVoiceMode(false);
        return;
      }

      // Ctrl+V - toggle voice mode (when not in input)
      if (e.key === 'v' && e.ctrlKey && document.activeElement?.tagName !== 'TEXTAREA') {
        e.preventDefault();
        toggleVoiceMode();
        return;
      }

      // Space - stop listening (when in voice mode)
      if (e.key === ' ' && isListening && document.activeElement?.tagName !== 'TEXTAREA') {
        e.preventDefault();
        stopListening();
        return;
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [handleInterrupt, toggleVoiceMode, isVoiceMode, isListening, stopListening, setVoiceMode]);

  return (
    <div className="flex flex-col h-screen">
      <Header onMenuClick={() => setSidebarOpen(true)} onInterrupt={handleInterrupt} isSpeaking={isSpeaking} />
      <div className="flex flex-1 overflow-hidden">
        <Sidebar isOpen={sidebarOpen} onClose={() => setSidebarOpen(false)} />
        <main className="flex-1 flex flex-col">
          <ChatContainer 
            messages={messages} 
            isLoading={isLoading} 
            onSuggestionClick={handleSend}
            onResubmit={handleSend}
            onBranch={(messageId) => {
              // Branch: Keep messages up to this point, clear after
              const messageIndex = messages.findIndex(m => m.id === messageId);
              if (messageIndex >= 0) {
                const messagesToKeep = messages.slice(0, messageIndex + 1);
                messagesToKeep.forEach(m => addMessage(m));
              }
            }}
          />
          <InputBar
            value={input}
            onChange={setInput}
            onSend={() => handleSend(input)}
            isLoading={isLoading}
            isListening={isListening}
            onVoiceToggle={toggleVoiceMode}
            isVoiceMode={isVoiceMode}
            selectedFile={selectedFile}
            onFileSelect={setSelectedFile}
            voiceResponseMode={voiceResponseMode}
            onVoiceResponseModeChange={setVoiceResponseMode}
          />
        </main>
      </div>
      {isVoiceMode && USE_LIVEKIT_VOICE && (
        <LiveKitAudio onClose={() => setVoiceMode(false)} />
      )}

      {isSettingsOpen && (
        <VoiceSettingsPanel onClose={() => setSettingsOpen(false)} />
      )}
    </div>
  );
}
