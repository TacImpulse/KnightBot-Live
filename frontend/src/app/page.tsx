'use client';

import { useState, useRef, useCallback, useEffect } from 'react';
import { Header } from '@/components/Header';
import { Sidebar } from '@/components/Sidebar';
import { ChatContainer } from '@/components/ChatContainer';
import { InputBar } from '@/components/InputBar';
import LiveKitAudio from '@/components/LiveKitAudio';
import { useStore } from '@/lib/store';
import { sendMessage, synthesizeSpeech, transcribeAudio } from '@/lib/api';

export default function Home() {
  const {
    messages, addMessage, updateMessage,
    isVoiceMode, setVoiceMode,
    isListening, setListening,
    isSpeaking, setSpeaking,
    isMuted, currentVoice, systemPrompt
  } = useStore();

  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);

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
      content: text + (selectedFile ? ` [Attached: ${selectedFile.name}]` : ''),
      timestamp: new Date()
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
      const response = await sendMessage(text, currentVoice || undefined, systemPrompt || undefined, images);
      updateMessage(assistantId, {
        content: response.text,
        isStreaming: false
      });

      // Text-to-speech if not muted (regardless of voice mode)
      if (!isMuted) {
        setSpeaking(true);
        try {
          const audioBlob = await synthesizeSpeech(response.text, 0.5, currentVoice || undefined);
          const audioUrl = URL.createObjectURL(audioBlob);
          const audio = new Audio(audioUrl);
          audioRef.current = audio;

          // Resume listening after speaking finishes (only if in voice mode)
          audio.onended = () => {
            setSpeaking(false);
            URL.revokeObjectURL(audioUrl);
            if (isVoiceMode) {
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
        // If muted but in voice mode, we still need to resume listening
        if (isVoiceMode) {
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
  }, [isLoading, isVoiceMode, isMuted, addMessage, updateMessage, setSpeaking, currentVoice, systemPrompt, selectedFile]);

  // Stop voice recording
  const stopListening = useCallback(() => {
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
      let silenceStart = Date.now();
      let isSpeakingDetected = false;
      const SILENCE_THRESHOLD = 2000; // 2 seconds of silence to stop
      const NOISE_THRESHOLD = 10; // Lowered threshold for better sensitivity
      
      const mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });
      
      // Request AudioContext access properly
      const AudioContextClass = window.AudioContext || (window as any).webkitAudioContext;
      const audioContext = new AudioContextClass();
      const source = audioContext.createMediaStreamSource(stream);
      const analyser = audioContext.createAnalyser();
      analyser.fftSize = 256;
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

        analyser.getByteFrequencyData(dataArray);
        const average = dataArray.reduce((a, b) => a + b) / bufferLength;

        // More aggressive VAD logic
        if (average > NOISE_THRESHOLD) {
          silenceStart = Date.now();
          if (!isSpeakingDetected) {
             console.log("🗣️ Speech detected!");
             isSpeakingDetected = true;
          }
        } else {
          if (isSpeakingDetected && (Date.now() - silenceStart > SILENCE_THRESHOLD)) {
             console.log("🤫 Silence detected, stopping...");
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
        
        const audioBlob = new Blob(chunksRef.current, { type: 'audio/webm' });
        stream.getTracks().forEach(t => t.stop());
        
        // Don't setListening(false) here immediately if we want to keep the "thinking" UI state
        // But for now, we do need to stop the visual indicator
        setListening(false);

        // Only process if:
        // 1. We have enough data
        // 2. We actually detected speech (or user manually stopped)
        // 3. AND we are still in voice mode (user didn't escape)
        if (audioBlob.size > 1000 && (isSpeakingDetected || !isVoiceMode)) { 
          try {
            // Play a small "pop" or "ping" sound here if we had one
            
            const result = await transcribeAudio(audioBlob);
            if (result.text && result.text.trim() && !result.error) {
              handleSend(result.text);
            } else if (result.error) {
               console.error('STT returned error:', result.error);
               // Resume listening if it was just silence/noise error
               if (isVoiceMode) startListening();
            } else {
               // Empty text (silence), resume listening
               if (isVoiceMode) startListening();
            }
          } catch (e) {
            console.error('STT failed:', e);
            if (isVoiceMode) startListening();
          }
        } else {
           // If we stopped but didn't detect speech (just silence timeout), restart listening
           if (isVoiceMode) {
               console.log("Restarting listener due to silence...");
               startListening();
           }
        }
      };

      mediaRecorder.start();
      setListening(true);
      checkAudioLevel(); // Start VAD loop
      
    } catch (e) {
      console.error('Microphone access denied:', e);
      alert('Microphone access is required for voice mode. Please allow microphone access and try again.');
    }
  }, [handleSend, setListening, stopListening, isVoiceMode]);

  // Interrupt Knight (stop audio playback)
  const handleInterrupt = useCallback(() => {
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.currentTime = 0;
      audioRef.current = null;
    }

    setSpeaking(false);

    if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'recording') {
      mediaRecorderRef.current.stop();
    }

    setListening(false);
  }, [setSpeaking, setListening]);

  // Toggle voice mode
  const toggleVoiceMode = useCallback(() => {
    if (isVoiceMode) {
      handleInterrupt();
      setVoiceMode(false);
    } else {
      setVoiceMode(true);
      startListening();
    }
  }, [isVoiceMode, handleInterrupt, setVoiceMode, startListening]);

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Escape - interrupt everything
      if (e.key === 'Escape') {
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

  // Click anywhere to interrupt when speaking
  useEffect(() => {
    const handleClick = () => {
      if (isSpeaking) handleInterrupt();
    };

    if (isSpeaking && isVoiceMode) {
      window.addEventListener('click', handleClick);
      return () => window.removeEventListener('click', handleClick);
    }
  }, [isSpeaking, isVoiceMode, handleInterrupt]);

  return (
    <div className="flex flex-col h-screen">
      <Header onMenuClick={() => setSidebarOpen(true)} onInterrupt={handleInterrupt} isSpeaking={isSpeaking} />
      <div className="flex flex-1 overflow-hidden">
        <Sidebar isOpen={sidebarOpen} onClose={() => setSidebarOpen(false)} />
        <main className="flex-1 flex flex-col">
          <ChatContainer messages={messages} isLoading={isLoading} onSuggestionClick={handleSend} />
          <InputBar
            value={input}
            onChange={setInput}
            onSend={() => handleSend(input)}
            isLoading={isLoading}
            isListening={isListening}
            onVoiceToggle={toggleVoiceMode}
            isVoiceMode={isVoiceMode}
            onStopListening={stopListening}
            selectedFile={selectedFile}
            onFileSelect={setSelectedFile}
          />
        </main>
      </div>
      {isVoiceMode && (
        <LiveKitAudio onClose={() => setVoiceMode(false)} />
      )}
    </div>
  );
}
