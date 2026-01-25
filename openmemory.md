# KnightBot Project Guide

## Overview
KnightBot is an "Ultimate Voice Bridge" (UVB) agent. It consists of a Next.js frontend and several Python microservices for STT (Parakeet), TTS (Chatterbox), and core logic (Knight API).

## Architecture
- **Frontend**: Next.js (`frontend/`) running on port 3000.
- **Knight API**: FastAPI (`scripts/knight_core.py`) running on port 8100.
- **Parakeet STT**: Python (`parakeet/server.py`) running on port 8070.
- **Chatterbox TTS**: Python (`chatterbox/server.py`) running on port 8060.
- **Infrastructure**: Docker Compose for Qdrant (6333) and Mem0 (8050).

## User Defined Namespaces
- frontend
- backend
- database
- infrastructure

## Components
- **Knight Core**: Orchestrates the conversation.
- **Parakeet**: Handles Speech-to-Text using NeMo/ONNX.
- **Chatterbox**: Handles Text-to-Speech using `chatterbox-tts`.
- **Pipeline**: `pipecat` based processing.

## Patterns
- **Startup**: `start.ps1` launches all services in separate PowerShell windows.
- **Installation**: `install.ps1` sets up venv and installs dependencies.
