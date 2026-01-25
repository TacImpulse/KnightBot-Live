# Contributing to KnightBot

First off, thank you for considering contributing to KnightBot! We want to make this project the *ultimate* open-source local AI companion, and your help is invaluable.

## 🛠️ Development Workflow (SOP)

To ensure code quality and stability across our multi-service architecture, please follow these Standard Operating Procedures.

### 1. Environment Setup
*   Always activate the shared virtual environment before running Python scripts:
    ```powershell
    & 'f:\KnightBot\venv\Scripts\Activate.ps1'
    ```
*   Ensure `Qdrant` and `LM Studio` are running before debugging backend logic.

### 2. Code Style
*   **Python**: We use `Black` formatting. Run `black .` in the respective service folder before committing.
*   **TypeScript/React**: Use `ESLint` and `Prettier`.
*   **Comments**: Comment complex logic. "Why" is more important than "What".

### 3. Making Changes
1.  **Create a Branch**: `git checkout -b feature/your-feature-name`
2.  **Microservices**: If modifying an API (e.g., `chatterbox`), ensure you update the client in `frontend/src/lib/api.ts` to match.
3.  **Testing**:
    *   **Unit**: Run local tests if available.
    *   **Integration**: Manually verify the full loop (Voice -> STT -> LLM -> TTS -> Audio Output).

### 4. Commit Guidelines
We follow Conventional Commits:
*   `feat: ...` for new features
*   `fix: ...` for bug fixes
*   `docs: ...` for documentation
*   `style: ...` for formatting
*   `refactor: ...` for code restructuring

### 5. Pull Requests
*   Push to your fork and submit a PR to `main`.
*   Include a description of changes and screenshots (if UI related).
*   Link to any relevant issues.

## 🐛 Reporting Bugs
*   Check existing issues first.
*   Provide logs! (Copy output from the relevant terminal: `frontend`, `chatterbox`, etc.)
*   State your OS, GPU, and RAM.

## 💡 Feature Requests
We love new ideas! Please open an issue with the tag `enhancement` and describe:
1.  The problem you're solving.
2.  Your proposed solution.
3.  Any alternatives you considered.

Happy Coding! 🚀
