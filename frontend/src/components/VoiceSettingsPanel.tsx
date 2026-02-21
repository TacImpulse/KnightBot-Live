'use client';

import { useState, useRef, useEffect, useCallback } from "react";
import { 
  X, Upload, Check, Image as ImageIcon, Edit2, PlayCircle, Scissors, Trash2, 
  User, Music, Mic, FileAudio, AlertCircle, Loader2, Save 
} from "lucide-react";
import { getVoices, uploadVoice, deleteVoice, uploadAvatar, renameVoice, selectVoice } from "@/lib/api";
import WaveSurfer from 'wavesurfer.js';
import RegionsPlugin from 'wavesurfer.js/dist/plugins/regions.esm.js';
import { motion, AnimatePresence } from "framer-motion";
import { useDropzone } from "react-dropzone";
import { toast, Toaster } from "sonner";
import { cn } from "@/lib/utils";

interface Props {
  onClose: () => void;
}

export function VoiceSettingsPanel({ onClose }: Props) {
  const [voices, setVoices] = useState<string[]>([]);
  const [selectedVoice, setSelectedVoice] = useState<string | null>(null);
  const [editingVoice, setEditingVoice] = useState<string | null>(null);
  const [editName, setEditName] = useState("");
  const [isRenameModalOpen, setIsRenameModalOpen] = useState(false);
  const [renameTarget, setRenameTarget] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  
  // Audio Editor State
  const [audioFile, setAudioFile] = useState<File | null>(null);
  const [isEditorOpen, setIsEditorOpen] = useState(false);
  const [trimRegion, setTrimRegion] = useState<{ start: number, end: number } | null>(null);
  const waveformRef = useRef<HTMLDivElement>(null);
  const wavesurfer = useRef<WaveSurfer | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);

  // Load Voices
  useEffect(() => {
    loadVoices();
  }, []);

  const loadVoices = async () => {
    try {
      const v = await getVoices();
      setVoices(v.voices);
      setSelectedVoice(v.default);
    } catch (e) {
      toast.error("Failed to load voices");
    }
  };

  // --- Dropzone Logic ---
  const onDrop = useCallback((acceptedFiles: File[]) => {
    const file = acceptedFiles[0];
    if (file) {
      setAudioFile(file);
      setIsEditorOpen(true);
    }
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'audio/wav': ['.wav'],
      'audio/mpeg': ['.mp3'],
      'audio/mp4': ['.m4a']
    },
    maxFiles: 1
  });

  // --- Audio Editor Logic ---
  useEffect(() => {
    if (isEditorOpen && audioFile && waveformRef.current) {
      if (wavesurfer.current) {
        wavesurfer.current.destroy();
      }

      const ws = WaveSurfer.create({
        container: waveformRef.current,
        waveColor: '#22d3ee', // Knight Cyan
        progressColor: '#a855f7', // Knight Purple
        cursorColor: '#ffffff',
        barWidth: 2,
        barGap: 3,
        height: 128,
        normalize: true,
      });

      const wsRegions = ws.registerPlugin(RegionsPlugin.create());

      ws.loadBlob(audioFile);

      ws.on('ready', () => {
        const duration = ws.getDuration();
        const end = Math.min(duration, 15);
        wsRegions.addRegion({
          start: 0,
          end: end,
          color: 'rgba(34, 211, 238, 0.2)',
          drag: true,
          resize: true,
        });
        setTrimRegion({ start: 0, end: end });
      });

      wsRegions.on('region-updated', (region) => {
        setTrimRegion({ start: region.start, end: region.end });
      });

      ws.on('finish', () => setIsPlaying(false));
      ws.on('play', () => setIsPlaying(true));
      ws.on('pause', () => setIsPlaying(false));

      wavesurfer.current = ws;

      return () => {
        ws.destroy();
      };
    }
  }, [isEditorOpen, audioFile]);

  const togglePlay = () => {
    wavesurfer.current?.playPause();
  };

  const handleEditorUpload = async () => {
    if (!audioFile) return;

    const nameInput = document.getElementById('voice-name-input') as HTMLInputElement;
    const name = nameInput?.value || audioFile.name.replace(/\.[^/.]+$/, "");

    if (!name.trim()) {
      toast.error("Please provide a name for the voice.");
      return;
    }

    setIsLoading(true);
    const toastId = toast.loading("Processing voice clone...");

    try {
      const fd = new FormData();
      fd.append('file', audioFile);
      fd.append('name', name);
      if (trimRegion) {
        fd.append('trim_start', trimRegion.start.toString());
        fd.append('trim_end', trimRegion.end.toString());
      }

      const r = await fetch('/api/tts/voices/upload', { method: 'POST', body: fd });
      if (!r.ok) throw new Error(await r.text());

      await loadVoices();
      toast.success("Voice profile created successfully!", { id: toastId });
      setIsEditorOpen(false);
      setAudioFile(null);
    } catch (err) {
      toast.error(`Upload failed: ${err}`, { id: toastId });
    } finally {
      setIsLoading(false);
    }
  };

  // --- Avatar Logic ---
  const handleAvatarUpload = async (voice: string, file: File) => {
    const toastId = toast.loading("Updating avatar...");
    try {
      await uploadAvatar(voice, file);
      // Force refresh by reloading voices
      await loadVoices(); 
      toast.success("Avatar updated", { id: toastId });
    } catch (err) {
      toast.error("Failed to upload avatar", { id: toastId });
    }
  };

  // --- Voice Management ---
  const openRenameModal = (voice: string) => {
    setRenameTarget(voice);
    setEditName(voice);
    setIsRenameModalOpen(true);
  };

  const performRename = async () => {
    if (!renameTarget || !editName.trim() || editName === renameTarget) {
      setIsRenameModalOpen(false);
      return;
    }
    
    const toastId = toast.loading("Renaming voice...");
    try {
      await renameVoice(renameTarget, editName);
      await loadVoices();
      toast.success(`Renamed to ${editName}`, { id: toastId });
      setIsRenameModalOpen(false);
    } catch (err) {
      toast.error("Failed to rename voice", { id: toastId });
    }
  };

  const handleDelete = async (voice: string) => {
    if (!confirm(`Are you sure you want to delete '${voice}'? This cannot be undone.`)) return;
    
    const toastId = toast.loading("Deleting voice...");
    try {
      await deleteVoice(voice);
      await loadVoices();
      toast.success("Voice deleted", { id: toastId });
    } catch (err) {
      toast.error("Failed to delete voice", { id: toastId });
    }
  };

  const handleSelect = async (voice: string) => {
    const toastId = toast.loading(`Activating ${voice}...`);
    try {
      await selectVoice(voice);
      await loadVoices();
      toast.success(`Active voice: ${voice}`, { id: toastId });
    } catch (err) {
      toast.error("Failed to change voice", { id: toastId });
    }
  };

  return (
    <AnimatePresence>
      <motion.div 
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 z-[100] flex items-center justify-center bg-black/80 backdrop-blur-md p-4"
      >
        <Toaster theme="dark" position="top-center" />
        
        <motion.div 
          initial={{ scale: 0.95, opacity: 0, y: 20 }}
          animate={{ scale: 1, opacity: 1, y: 0 }}
          exit={{ scale: 0.95, opacity: 0, y: 20 }}
          className="bg-[#0A0A0B] w-full max-w-5xl h-[85vh] rounded-3xl border border-white/10 shadow-2xl flex flex-col overflow-hidden relative"
        >
          {/* Header */}
          <div className="flex justify-between items-center p-6 border-b border-white/10 bg-white/5 backdrop-blur-xl sticky top-0 z-10">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-cyan-500 to-purple-600 flex items-center justify-center shadow-lg shadow-cyan-500/20">
                <Music className="w-5 h-5 text-white" />
              </div>
              <div>
                <h2 className="text-xl font-bold text-white tracking-tight">Neural Studio</h2>
                <p className="text-gray-400 text-xs font-medium uppercase tracking-wider">Voice Synthesis & Identity Engine</p>
              </div>
            </div>
            <button 
              onClick={onClose} 
              className="p-2.5 bg-white/5 hover:bg-white/10 rounded-full text-gray-400 hover:text-white transition-all hover:rotate-90"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          <div className="flex-1 overflow-y-auto p-8 space-y-8 custom-scrollbar">
            
            {/* Upload Zone */}
            <section className="space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-semibold text-white flex items-center gap-2">
                  <Mic className="w-5 h-5 text-cyan-400" /> Cloning Laboratory
                </h3>
                <span className="text-xs px-2 py-1 rounded bg-cyan-500/10 text-cyan-400 border border-cyan-500/20">
                  WAV / MP3 / M4A Supported
                </span>
              </div>

              <div 
                {...getRootProps()} 
                className={`
                  relative border-2 border-dashed rounded-2xl p-8 transition-all duration-300 cursor-pointer group
                  flex flex-col items-center justify-center gap-4
                  ${isDragActive 
                    ? 'border-cyan-500 bg-cyan-500/10 scale-[1.01]' 
                    : 'border-white/10 bg-white/5 hover:border-white/20 hover:bg-white/[0.07]'}
                `}
              >
                <input {...getInputProps()} />
                <div className="w-16 h-16 rounded-full bg-gradient-to-br from-gray-800 to-black border border-white/10 flex items-center justify-center shadow-inner group-hover:scale-110 transition-transform duration-300">
                  <Upload className={`w-7 h-7 ${isDragActive ? 'text-cyan-400' : 'text-gray-400 group-hover:text-white'}`} />
                </div>
                <div className="text-center space-y-1">
                  <p className="text-lg font-medium text-white">
                    {isDragActive ? "Drop the sample here..." : "Drag & drop voice sample"}
                  </p>
                  <p className="text-sm text-gray-400">or click to browse your files</p>
                </div>
              </div>
            </section>

            {/* Voice Grid */}
            <section className="space-y-4">
              <h3 className="text-lg font-semibold text-white flex items-center gap-2">
                <User className="w-5 h-5 text-purple-400" /> Identity Matrix
              </h3>

              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
                {voices.map(voice => (
                  <motion.div 
                    layoutId={voice}
                    key={voice}
                    initial={{ opacity: 0, scale: 0.9 }}
                    animate={{ opacity: 1, scale: 1 }}
                    className={`
                      relative group bg-[#121214] border rounded-2xl p-4 transition-all duration-300
                      hover:shadow-2xl hover:-translate-y-1
                      ${voice === selectedVoice 
                        ? 'border-cyan-500/50 shadow-[0_0_30px_-10px_rgba(6,182,212,0.3)]' 
                        : 'border-white/5 hover:border-white/20'}
                    `}
                  >
                    {voice === selectedVoice && (
                      <div className="absolute top-3 right-3 flex items-center gap-1.5 px-2.5 py-1 bg-cyan-500/10 border border-cyan-500/20 rounded-full">
                        <div className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-pulse" />
                        <span className="text-[10px] font-bold text-cyan-400 uppercase tracking-wide">Active</span>
                      </div>
                    )}

                    <div className="flex items-start gap-4">
                      {/* Avatar */}
                      <div className="relative group/avatar">
                        <div className="w-16 h-16 rounded-2xl overflow-hidden border-2 border-white/10 bg-black relative z-10">
                          <img 
                            src={`/api/tts/voices/${voice}/avatar?t=${Date.now()}`} 
                            alt={voice}
                            className="w-full h-full object-cover"
                            onError={(e) => {
                              (e.target as HTMLImageElement).src = `https://api.dicebear.com/7.x/bottts/svg?seed=${voice}&baseColor=121214`;
                            }}
                          />
                          <div className="absolute inset-0 bg-black/50 opacity-0 group-hover/avatar:opacity-100 transition-opacity flex items-center justify-center">
                            <label className="cursor-pointer p-2 hover:bg-white/20 rounded-full transition-colors">
                              <ImageIcon className="w-4 h-4 text-white" />
                              <input 
                                type="file" 
                                className="hidden" 
                                accept="image/*"
                                onChange={(e) => e.target.files?.[0] && handleAvatarUpload(voice, e.target.files[0])}
                              />
                            </label>
                          </div>
                        </div>
                        {/* Glow behind avatar */}
                        <div className="absolute inset-0 bg-gradient-to-br from-cyan-500 to-purple-600 blur-xl opacity-20 -z-10 rounded-full group-hover:opacity-40 transition-opacity" />
                      </div>

                      <div className="flex-1 min-w-0 pt-1">
                        <h4 className="text-white font-bold text-lg truncate mb-1">{voice}</h4>
                        <div className="flex items-center gap-2">
                           {voice !== selectedVoice && (
                             <button 
                               onClick={() => handleSelect(voice)}
                               className="text-xs bg-white/5 hover:bg-cyan-500/20 hover:text-cyan-400 text-gray-400 px-3 py-1.5 rounded-lg transition-colors font-medium border border-white/5 hover:border-cyan-500/30"
                             >
                               Activate
                             </button>
                           )}
                        </div>
                      </div>
                    </div>

                    {/* Action Bar (Slide up on hover) */}
                    <div className="mt-4 pt-3 border-t border-white/5 flex justify-end gap-2 opacity-60 group-hover:opacity-100 transition-opacity">
                      <button 
                        onClick={() => openRenameModal(voice)}
                        className="p-2 hover:bg-white/10 rounded-lg text-gray-400 hover:text-white transition-colors"
                        title="Rename"
                      >
                        <Edit2 className="w-4 h-4" />
                      </button>
                      <button 
                        onClick={() => handleDelete(voice)}
                        className="p-2 hover:bg-red-500/10 rounded-lg text-gray-400 hover:text-red-400 transition-colors"
                        title="Delete"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </motion.div>
                ))}
              </div>
              
              {voices.length === 0 && (
                <div className="flex flex-col items-center justify-center py-20 border border-dashed border-white/10 rounded-3xl bg-white/[0.02]">
                  <div className="w-16 h-16 rounded-full bg-white/5 flex items-center justify-center mb-4">
                    <FileAudio className="w-8 h-8 text-gray-600" />
                  </div>
                  <p className="text-gray-400 font-medium">No voice profiles detected</p>
                  <p className="text-gray-600 text-sm mt-1">Upload a sample to initialize the neural engine</p>
                </div>
              )}
            </section>
          </div>

          {/* --- Editor Modal --- */}
          <AnimatePresence>
            {isEditorOpen && audioFile && (
              <motion.div 
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="absolute inset-0 z-[110] bg-[#0A0A0B] flex flex-col"
              >
                <div className="flex items-center justify-between p-6 border-b border-white/10">
                  <h3 className="text-xl font-bold text-white flex items-center gap-3">
                    <Scissors className="w-5 h-5 text-purple-400" /> Audio Laboratory
                  </h3>
                  <button onClick={() => setIsEditorOpen(false)} className="text-gray-400 hover:text-white">
                    <X className="w-6 h-6" />
                  </button>
                </div>

                <div className="flex-1 p-8 flex flex-col justify-center">
                  <div className="max-w-4xl mx-auto w-full space-y-8">
                    
                    <div className="bg-[#121214] border border-white/10 rounded-2xl p-6 shadow-2xl relative overflow-hidden">
                       {/* Waveform Container */}
                       <div ref={waveformRef} className="w-full" />
                       
                       {/* Play Overlay if needed or controls below */}
                    </div>

                    <div className="grid grid-cols-2 gap-8">
                      <div className="space-y-2">
                        <label className="text-sm font-medium text-gray-400 uppercase tracking-wider">Voice Name</label>
                        <input 
                          id="voice-name-input"
                          type="text" 
                          defaultValue={audioFile.name.replace(/\.[^/.]+$/, "")}
                          className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-white focus:outline-none focus:border-cyan-500/50 focus:bg-white/10 transition-all placeholder:text-gray-600"
                          placeholder="e.g. Jarvis V1"
                        />
                      </div>

                      <div className="flex items-end justify-between">
                         <div className="space-y-1">
                           <p className="text-gray-400 text-sm">Selection Duration</p>
                           <p className="text-2xl font-mono text-cyan-400">
                             {trimRegion ? (trimRegion.end - trimRegion.start).toFixed(2) : '0.00'}s
                           </p>
                         </div>
                         
                         <button 
                           onClick={togglePlay}
                           className={`
                             h-12 px-6 rounded-xl flex items-center gap-2 font-bold transition-all
                             ${isPlaying 
                               ? 'bg-purple-500/20 text-purple-400 border border-purple-500/30' 
                               : 'bg-white/5 text-white border border-white/10 hover:bg-white/10'}
                           `}
                         >
                           {isPlaying ? <span className="animate-pulse">Playing...</span> : <><PlayCircle className="w-5 h-5" /> Preview</>}
                         </button>
                      </div>
                    </div>

                  </div>
                </div>

                <div className="p-6 border-t border-white/10 bg-white/5 flex justify-end gap-3">
                  <button 
                    onClick={() => setIsEditorOpen(false)}
                    className="px-6 py-3 rounded-xl font-medium text-gray-400 hover:text-white hover:bg-white/5 transition-colors"
                  >
                    Cancel
                  </button>
                  <button 
                    onClick={handleEditorUpload}
                    disabled={isLoading}
                    className="px-8 py-3 rounded-xl bg-gradient-to-r from-cyan-600 to-purple-600 text-white font-bold shadow-lg shadow-purple-500/20 hover:shadow-purple-500/40 hover:scale-[1.02] transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
                  >
                    {isLoading ? <Loader2 className="w-5 h-5 animate-spin" /> : <Save className="w-5 h-5" />}
                    {isLoading ? 'Processing...' : 'Save Voice Profile'}
                  </button>
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          {/* --- Rename Modal --- */}
          <AnimatePresence>
            {isRenameModalOpen && (
              <div className="absolute inset-0 z-[120] bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
                <motion.div 
                  initial={{ scale: 0.9, opacity: 0 }}
                  animate={{ scale: 1, opacity: 1 }}
                  exit={{ scale: 0.9, opacity: 0 }}
                  className="bg-[#18181b] border border-white/10 p-6 rounded-2xl w-full max-w-md shadow-2xl"
                >
                  <h3 className="text-lg font-bold text-white mb-4">Rename Voice</h3>
                  <input 
                    value={editName}
                    onChange={(e) => setEditName(e.target.value)}
                    className="w-full bg-black/50 border border-white/10 rounded-xl px-4 py-3 text-white mb-6 focus:outline-none focus:border-cyan-500"
                    autoFocus
                    onKeyDown={(e) => e.key === 'Enter' && performRename()}
                  />
                  <div className="flex justify-end gap-3">
                    <button 
                      onClick={() => setIsRenameModalOpen(false)}
                      className="px-4 py-2 text-gray-400 hover:text-white"
                    >
                      Cancel
                    </button>
                    <button 
                      onClick={performRename}
                      className="px-6 py-2 bg-cyan-600 hover:bg-cyan-500 text-white rounded-lg font-medium"
                    >
                      Confirm
                    </button>
                  </div>
                </motion.div>
              </div>
            )}
          </AnimatePresence>

        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}
