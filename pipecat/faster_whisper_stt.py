"""KnightBot Custom Faster Whisper STT Service for Pipecat

This module provides a native Faster Whisper STT service for Pipecat pipelines.
It extends the base STTService class to integrate Faster Whisper directly.

Usage:
    from pipecat.faster_whisper_stt import FasterWhisperSTT
    
    stt = FasterWhisperSTT(
        model="large-v3",
        device="cuda"
    )
"""

import os
import torch
from typing import Optional

from pipecat.services.stt_service import STTService
from pipecat.transcriptions.language import Language

# Try to import faster-whisper
try:
    from faster_whisper import WhisperModel
    _FASTER_WHISPER_AVAILABLE = True
except ImportError:
    _FASTER_WHISPER_AVAILABLE = False
    WhisperModel = None


class FasterWhisperSTT(STTService):
    """Faster Whisper STT Service for Pipecat.
    
    A native Pipecat STT service that uses Faster Whisper for speech recognition.
    This runs directly in the Pipecat pipeline without HTTP overhead.
    
    Args:
        model: Model size (tiny, base, small, medium, large-v1, large-v2, large-v3)
               Default: large-v3
        device: Device to use (cuda or cpu)
                Default: cuda if available, else cpu
        compute_type: Compute type (float16, int8, int8_float16)
                      Default: float16 for CUDA, int8 for CPU
        language: Optional language code (e.g., "en")
        sample_rate: Audio sample rate (default: 16000)
    """
    
    def __init__(
        self,
        model: str = "large-v3",
        device: Optional[str] = None,
        compute_type: Optional[str] = None,
        language: Optional[str] = None,
        sample_rate: int = 16000,
        **kwargs
    ):
        if not _FASTER_WHISPER_AVAILABLE:
            raise ImportError(
                "faster-whisper is not installed. "
                "Install with: pip install faster-whisper"
            )
        
        # Determine device
        if device is None:
            device = "cuda" if torch.cuda.is_available() else "cpu"
        
        # Determine compute type
        if compute_type is None:
            compute_type = "float16" if device == "cuda" else "int8"
        
        # Store config
        self._model_name = model
        self._device = device
        self._compute_type = compute_type
        self._language = language
        self._sample_rate = sample_rate
        
        # Will be loaded on first use
        self._model = None
        
        # Initialize base class
        super().__init__(
            sample_rate=sample_rate,
            **kwargs
        )
        
        # Set language if provided
        if language:
            self.set_language(language)
    
    async def run_stt(self, audio: bytes) -> str:
        """Run STT on audio bytes.
        
        Args:
            audio: Raw audio bytes (PCM 16-bit, 16kHz, mono)
            
        Returns:
            Transcribed text
        """
        # Load model on first use
        if self._model is None:
            await self._load_model()
        
        # Transcribe audio
        segments, info = self._model.transcribe(
            audio,
            language=self._language,
            beam_size=5,
            vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=500)
        )
        
        # Collect all segments
        text_parts = []
        for segment in segments:
            text_parts.append(segment.text.strip())
        
        return " ".join(text_parts)
    
    async def _load_model(self):
        """Load the Faster Whisper model."""
        import asyncio
        
        # Run model loading in executor to avoid blocking
        loop = asyncio.get_event_loop()
        self._model = await loop.run_in_executor(
            None,
            self._load_model_sync
        )
    
    def _load_model_sync(self):
        """Synchronous model loading."""
        print(f"📦 Loading Faster Whisper: {self._model_name} on {self._device}")
        if self._device == "cuda" and torch.cuda.is_available():
            print(f"   GPU: {torch.cuda.get_device_name(0)}")
        
        self._model = WhisperModel(
            self._model_name,
            device=self._device,
            compute_type=self._compute_type
        )
        print("✓ Faster Whisper model loaded")
    
    def set_language(self, language: str):
        """Set the language for transcription."""
        self._language = language
        # Also set in base class if available
        try:
            from pipecat.transcriptions.language import Language
            self.language = Language(language)
        except Exception:
            pass


# Convenience function to create the service
def create_faster_whisper_stt(
    model: str = None,
    device: str = None,
    language: str = None,
    **kwargs
) -> FasterWhisperSTT:
    """Create a Faster Whisper STT service.
    
    Args:
        model: Model name (default from env KB_FASTER_WHISPER_MODEL or large-v3)
        device: Device (default from env KB_FASTER_WHISPER_DEVICE or auto)
        language: Language code (optional)
        **kwargs: Additional arguments passed to FasterWhisperSTT
        
    Returns:
        FasterWhisperSTT instance
    """
    # Get from environment or defaults
    model = model or os.getenv("KB_FASTER_WHISPER_MODEL", "large-v3")
    device = device or os.getenv("KB_FASTER_WHISPER_DEVICE", "cuda" if torch.cuda.is_available() else "cpu")
    
    return FasterWhisperSTT(
        model=model,
        device=device,
        language=language,
        **kwargs
    )
