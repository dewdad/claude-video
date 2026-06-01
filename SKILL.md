---
name: watch
description: |
  Ingest video and audio files. Extracts text, frames, and scene cuts from any
  media source (URL or local path) using yt-dlp, ffmpeg, Whisper, and multimodal
  AI — the one-stop skill for AI agents to understand media.

  Triggers when user mentions:
  - "/watch <url-or-path>"
  - "watch this video", "watch this clip", "ingest this video"
  - "transcribe this video", "summarize this video", "what happens at <time> in this video"
  - "analyze this recording", "what's in this screencast", "diagnose this bug video"
argument-hint: "<video-url-or-path> [question]"
allowed-tools: Bash, Read, AskUserQuestion
homepage: https://github.com/dewdad/media-ingest
repository: https://github.com/dewdad/media-ingest
author: dewdad
license: MIT
user-invocable: true
---

# /watch — Watch a video

A Python script downloads media, extracts JPEG frames + a timestamped transcript, and prints frame paths. You then `Read` each frame (parallel) and combine with the transcript to answer.

`$SKILL_DIR` = directory containing this file (auto-resolved by OpenCode; `$CLAUDE_SKILL_DIR` for Claude Code). On Windows substitute `python` for `python3`.

## Layout & config

- **`scripts/`** — reusable, idempotent Python entry points. `watch.py` is the orchestrator; `setup.py` is the installer/preflight; the rest (`download`, `frames`, `transcribe`, `whisper`, `multimodal`) are standalone modules you can also invoke directly for debugging.
- **`.env.example`** — defines the minimum config. Copy to `~/.config/watch/.env` (preferred, 0600) or a project-local `.env`. `setup.py` scaffolds the canonical file automatically; the example is for reference and CI.
- **Capability inference** — the skill infers what it can do from the available config. With no keys, it runs frames-only when captions are missing. Add `GROQ_API_KEY` to enable Whisper, `MULTIMODAL_API_KEY` to enable multimodal A/V analysis. Each backend lights up independently as keys appear in `.env`.

## Step 0 — Preflight (silent on success)

```bash
python3 "$SKILL_DIR/scripts/setup.py" --check
```

Exit 0 → proceed silently to Step 1. **Do not announce success.** On non-zero exit, run the installer (idempotent; auto-installs ffmpeg/yt-dlp via brew on macOS, prints commands on Linux/Windows; scaffolds `~/.config/watch/.env` at 0600):

```bash
python3 "$SKILL_DIR/scripts/setup.py"
```

If a key is still missing after install, use `AskUserQuestion`. Preferred: Groq (cheap/fast), then OpenAI, then multimodal (NVIDIA NIM). Write to `~/.config/watch/.env` as `GROQ_API_KEY`, `OPENAI_API_KEY`, or `MULTIMODAL_API_KEY`. If user declines all, run with `--no-whisper --no-multimodal` (frames-only when no captions).

Skip Step 0 on follow-up `/watch` calls within a session — once `--check` returned 0, nothing changes between turns.

→ Exit codes, `--json` schema, and full failure matrix: `references/failure-handling.md`

## When to use

User pastes a video URL (any yt-dlp-supported site), points at a local media file, or types `/watch <source> [question]`.

## Invocation

**Step 1.** Parse user input → `source` + optional `question`.

**Step 2.** Run:

```bash
python3 "$SKILL_DIR/scripts/watch.py" "<source>" [flags]
```

Common flags:

| Flag | Purpose |
|------|---------|
| `--start T` / `--end T` | Focus a section (`SS`, `MM:SS`, `HH:MM:SS`); auto-densifies fps |
| `--max-frames N` | Lower cap for tighter token budget |
| `--resolution W` | Frame width px (default 512; 1024 only for on-screen text) |
| `--whisper groq\|openai` | Force backend |
| `--multimodal` / `--multimodal-audio` | Use multimodal (joint A/V; audio mode for > 2 min) |
| `--no-whisper` / `--no-multimodal` | Disable a backend |

→ Full flag list, fps overrides, custom out-dir, multimodal model/endpoint overrides: `references/backends.md`

**Step 3.** Read every printed frame path in a single message (parallel calls). Frames are chronological with `t=MM:SS` absolute timestamps.

**Step 4.** Answer using both streams: frames (visual) + transcript (header shows source: `captions` / `whisper (groq|openai)` / `multimodal`). Cite timestamps. If no question, summarize structure, key moments, visuals, dialogue.

**Step 5.** Cleanup: `rm -rf <working-dir>` unless follow-ups likely.

## When to focus a section

Pass `--start` / `--end` for: explicit time ranges in the question, long videos with localized questions, or re-runs needing more detail. Focused mode is denser (still capped at 2 fps) and far more useful than a sparse full scan on long videos.

→ Frame budgets and focused-mode tables: `references/frame-budgets.md`

## Transcription

Priority chain: **native captions → Whisper (Groq → OpenAI) → multimodal**. Override with `--multimodal` to use directly, `--no-multimodal` to skip. All keys live in `~/.config/watch/.env`.

→ Backend details, audio extraction params, NVIDIA NIM config: `references/backends.md`

## Token efficiency

Frames dominate cost: ~50–80k image tokens for 80 frames @ 512 px. Transcript is cheap (few k tokens). `--resolution 1024` ≈ 4× tokens/frame — only when needed. **If you already watched a video this session, do not re-run; answer from existing context.**

## Failure handling

If something fails, consult the matrix before retrying blindly.

→ `references/failure-handling.md`

## Security

Runs locally: yt-dlp (download + captions), ffmpeg/ffprobe (frames + audio). Sends only extracted audio to Whisper providers; video itself is uploaded only to the multimodal endpoint, only in video mode (≤ 2 min). Keys stored at `~/.config/watch/.env` (0600); never logged.

→ Full disclosure and bundled-script inventory: `references/security.md`
