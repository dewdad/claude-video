# media-ingest

**One-stop media ingestion for AI agents. Free to use. Easy to install.**

Extract text, frames, and scene context from any video or audio source — URLs or local files.

## Quick Install

**Skillshare (recommended — works across Claude, OpenCode, Cursor, Gemini, and 9+ AI tools):**
```bash
skillshare install github.com/dewdad/media-ingest
skillshare sync
```

**Claude Code:**
```
/plugin marketplace add dewdad/media-ingest
/plugin install watch@media-ingest
```

**Manual / dev:**
```bash
git clone https://github.com/dewdad/media-ingest.git ~/.claude/skills/watch
```

Zero config to start — `yt-dlp` and `ffmpeg` install on first run via `brew` on macOS (Linux/Windows print exact commands). Captions cover most public videos for free. API keys are only needed when a video has no captions.

---

## What this does

AI agents can read text, run code, browse the web — but they can't natively *see* or *hear* media files. `media-ingest` closes that gap:

1. **Downloads** from any URL (YouTube, Loom, TikTok, X, Instagram, Vimeo, + hundreds more via yt-dlp) or reads a local file directly.
2. **Extracts frames** at an auto-scaled rate with smart frame budgets per duration.
3. **Extracts text** via multiple fallback backends: native captions → Groq Whisper → OpenAI Whisper → multimodal AI analysis.
4. **Hands everything to the agent** — timestamped frames + full transcript — so it can answer grounded in what it *actually saw and heard*.

## Use cases

- **Summarize a video.** `/watch https://youtu.be/<long-thing> summarize this`
- **Analyze content structure.** `/watch https://youtu.be/<viral-video> what hook did they open with?`
- **Diagnose bugs from recordings.** `/watch bug-repro.mov what's going wrong?`
- **Transcribe podcasts.** `/watch podcast.mp3 key takeaways?`
- **Extract audio insights.** `/watch --multimodal-audio interview.mp4` — captures non-speech audio, music, ambient sounds.

## Usage

```
/watch https://youtu.be/dQw4w9WgXcQ what happens at the 30 second mark?
/watch ~/Movies/screen-recording.mp4 when does the UI break?
/watch podcast.mp3 summarize the key points
/watch https://www.tiktok.com/@user/video/123 summarize this
```

Focused on a specific section — denser frame budget, lower token cost:
```
/watch https://youtu.be/abc --start 2:15 --end 2:45
/watch video.mp4 --start 50 --end 60
```

### Flags

| Flag | Purpose |
|------|---------|
| `--max-frames N` | Lower the frame cap for tighter token budget |
| `--resolution W` | Bump frame width (e.g., 1024) to read on-screen text |
| `--fps F` | Override auto-fps calculation (capped at 2) |
| `--whisper groq\|openai` | Force a specific Whisper backend |
| `--no-whisper` | Disable Whisper; frames only |
| `--multimodal` | Use multimodal AI (audio+visual, ≤2 min video) |
| `--multimodal-audio` | Force audio-only multimodal (up to 1 hr) |
| `--no-multimodal` | Disable multimodal fallback |
| `--multimodal-model MODEL` | Override multimodal model |
| `--multimodal-base-url URL` | Override multimodal API endpoint |
| `--start TIME` | Start time (seconds or MM:SS or HH:MM:SS) |
| `--end TIME` | End time |

## Transcription backends

| Backend | Key | Cost | Best for |
|---------|-----|------|----------|
| Native captions | None | Free | Public videos with subtitles |
| Groq Whisper | `GROQ_API_KEY` | Cheap, fast | Speech transcription |
| OpenAI Whisper | `OPENAI_API_KEY` | Standard | Whisper fallback |
| Multimodal (NVIDIA NIM) | `MULTIMODAL_API_KEY` | Free tier | Audio+visual understanding, non-speech audio |

Priority chain: captions → Whisper → multimodal. All keys go in `~/.config/watch/.env`.

The multimodal backend is provider-agnostic — works with any OpenAI-compatible endpoint:
```env
MULTIMODAL_API_KEY=nvapi-...
MULTIMODAL_BASE_URL=https://integrate.api.nvidia.com/v1  # or OpenRouter, local vLLM, etc.
MULTIMODAL_MODEL=nvidia/nemotron-3-nano-omni-30b-a3b-reasoning
```

## Frame budget

| Duration | Frames | Coverage |
|----------|--------|----------|
| ≤30 s | ~30 | Dense — every key moment |
| 30 s - 1 min | ~40 | Still dense |
| 1 - 3 min | ~60 | Comfortable |
| 3 - 10 min | ~80 | Sparse but workable |
| > 10 min | 100 | Sparse scan — use `--start`/`--end` for focus |

## First run

On first `/watch` call, the skill auto-installs `ffmpeg` + `yt-dlp` (macOS via brew) and scaffolds `~/.config/watch/.env`. After that, preflight is silent and sub-100ms.

## Structure

```
.
├── SKILL.md                 # skill contract
├── scripts/
│   ├── watch.py             # entry point — orchestrates download → frames → transcript
│   ├── download.py          # yt-dlp wrapper
│   ├── frames.py            # ffmpeg frame extraction + auto-fps logic
│   ├── transcribe.py        # VTT parsing + dedupe + Whisper orchestration
│   ├── whisper.py           # Groq / OpenAI clients (pure stdlib)
│   ├── multimodal.py        # Provider-agnostic multimodal client (default: NVIDIA NIM)
│   ├── setup.py             # preflight + installer
│   └── build-skill.sh       # build dist/watch.skill for claude.ai upload
├── hooks/                   # SessionStart status hook
├── .opencode-plugin/        # OpenCode plugin manifest
├── .claude-plugin/          # Claude Code plugin manifest
├── .codex-plugin/           # Codex packaging
└── .github/workflows/       # auto-builds watch.skill on tag push
```

## License

MIT. Fork of [bradautomates/claude-video](https://github.com/bradautomates/claude-video).

Built on `yt-dlp`, `ffmpeg`, Whisper (Groq/OpenAI), and NVIDIA Nemotron.

---

[github.com/dewdad/media-ingest](https://github.com/dewdad/media-ingest) · [LICENSE](LICENSE)
