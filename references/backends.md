# Transcription backends

Priority chain: **native captions → Whisper → multimodal**. Override with `--multimodal` (use directly) or `--no-multimodal` (skip).

## 1. Native captions (free, preferred)

`yt-dlp` pulls manual or auto-generated subtitles when the source platform exposes them. No API call, no key.

## 2. Whisper API

Used when captions are missing or source is a local file. Audio extraction:

```
ffmpeg -vn -ac 1 -ar 16000 -b:a 64k    # mono, 16 kHz, ~0.5 MB/min
```

| Backend | Model | Endpoint | Key | Notes |
|---------|-------|----------|-----|-------|
| Groq | `whisper-large-v3` | `api.groq.com/openai/v1/audio/transcriptions` | `GROQ_API_KEY` | Default — cheaper, faster. Get key at console.groq.com/keys |
| OpenAI | `whisper-1` | `api.openai.com/v1/audio/transcriptions` | `OPENAI_API_KEY` | Fallback. Get key at platform.openai.com/api-keys |

25 MB upload cap on long audio.

## 3. Multimodal (fallback or `--multimodal`)

Joint audio+visual understanding. Advantages over Whisper:
- Understands non-speech audio (music, SFX, ambient)
- Correlates audio with visuals
- Identifies speakers from visual context

**Limitation:** reasoning is disabled for media inputs on NVIDIA NIM — the model describes/transcribes but cannot reason deeply. The agent does the reasoning.

| Mode | Limit | Trigger |
|------|-------|---------|
| Video | ≤ 2 min | `--multimodal` on short videos |
| Audio | ≤ 1 hr | `--multimodal-audio`, or auto on > 2 min videos |

Provider-agnostic — works with any OpenAI-compatible multimodal endpoint. Config in `~/.config/watch/.env`:

```
MULTIMODAL_API_KEY=...                                          # required (legacy: NGC_API_KEY)
MULTIMODAL_BASE_URL=https://integrate.api.nvidia.com/v1         # default
MULTIMODAL_MODEL=nvidia/nemotron-3-nano-omni-30b-a3b-reasoning  # default
```

Swap providers (OpenRouter, local vLLM, etc.) by overriding `MULTIMODAL_BASE_URL` or `--multimodal-base-url`.

## All flags

| Flag | Purpose |
|------|---------|
| `--start T` / `--end T` | Focus a section (`SS`, `MM:SS`, `HH:MM:SS`); auto-densifies fps |
| `--max-frames N` | Lower cap for tighter token budget |
| `--resolution W` | Frame width px (default 512; 1024 for on-screen text only) |
| `--fps F` | Override auto-fps (max 2) |
| `--out-dir DIR` | Custom working dir |
| `--whisper groq\|openai` | Force backend |
| `--no-whisper` | Disable Whisper |
| `--multimodal` | Multimodal mode |
| `--multimodal-audio` | Force audio-only multimodal |
| `--no-multimodal` | Disable multimodal fallback |
| `--multimodal-model MODEL` | Override model |
| `--multimodal-base-url URL` | Override endpoint |
