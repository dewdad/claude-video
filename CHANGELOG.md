# Changelog

All notable changes to `/watch` are documented here.

## [0.2.0] — 2026-06-01

### Added
- **Multimodal backend** (`scripts/multimodal.py`) for joint audio+visual understanding, including non-speech audio (music, SFX, ambient). Provider-agnostic — works with any OpenAI-compatible endpoint. Default: NVIDIA NIM (Nemotron-3-Nano-Omni). Flags: `--multimodal`, `--multimodal-audio`, `--no-multimodal`, `--multimodal-model`, `--multimodal-base-url`.
- **OpenCode support**: portable `$SKILL_DIR` resolution and `.opencode-plugin/plugin.json`.
- **`.env.example`** at repo root documenting all environment variables (`GROQ_API_KEY`, `OPENAI_API_KEY`, `MULTIMODAL_API_KEY`, `MULTIMODAL_BASE_URL`, `MULTIMODAL_MODEL`).
- **`references/`** directory with cold-path docs (`frame-budgets.md`, `failure-handling.md`, `backends.md`, `security.md`) loaded on demand to keep `SKILL.md` lean.
- Trigger phrases in skill description so agents know when to invoke `/watch`.

### Changed
- Renamed repo from `claude-video` to `media-ingest`. Plugin manifests, marketplace metadata, and homepage updated to `dewdad/media-ingest`.
- `SKILL.md` rewritten for token efficiency (~63% smaller); cold-path content moved to `references/`.
- Transcription priority chain is now: native captions → Whisper (Groq → OpenAI) → multimodal.
- `.gitignore` now ignores `.env` (allow-lists `.env.example`).
- SessionStart hook now reads keys from project-local `.env` as a fallback (matches Python script behavior).

### Fixed
- `.claude-plugin` manifests synced to current repo, author, and description (previously stuck on upstream `bradautomates/claude-video`).
- `enhancement-validation/` now `export-ignore`d so it doesn't ship in install bundles.
- SessionStart hook uses BSD `stat` first on macOS (the documented default platform).

## [0.1.2] — 2026-04-24

### Fixed
- Windows console crash: removed the emoji from the long-video warning in `watch.py`; cp1252 consoles couldn't encode it.
- `setup.py` now prints `winget` / `pip` install commands on Windows instead of "unsupported platform" — matches what the README already promised.

### Changed
- `SKILL.md` notes that on Windows the scripts must be invoked with `python`, not `python3` (the latter is the Microsoft Store stub on Windows).

## [0.1.1] — 2026-04-24

### Fixed
- Added `commands/watch.md` shim so `/watch` is callable when installed as a Claude Code plugin. Without it, the plugin loaded but the skill wasn't exposed as a slash command.
- `scripts/build-skill.sh` now strips `commands/` from the claude.ai `.skill` bundle alongside `hooks/` and `.claude-plugin/`.

## [0.1.0] — 2026-04-24

Initial marketplace release.

### Added
- `/watch <url-or-path> [question]` slash command.
- yt-dlp download with native caption extraction (manual + auto-subs).
- ffmpeg frame extraction with auto-scaled fps (≤2 fps, ≤100 frames, duration-aware budget).
- `--start` / `--end` focused mode with denser frame budget and transcript range filtering.
- Whisper fallback (Groq preferred, OpenAI secondary) for videos without captions.
- `setup.py` preflight: silent `--check`, structured `--json`, and installer that auto-runs `brew install` on macOS.
- Session-start hook that prints a one-line status on first run / partial config.
- `.skill` bundle packaging for claude.ai upload via `scripts/build-skill.sh`.
