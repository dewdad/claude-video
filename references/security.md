# Security & permissions

## What the skill does

- Runs `yt-dlp` locally to download video and pull native captions (request goes directly to whatever host the URL points at)
- Runs `ffmpeg` / `ffprobe` locally to extract JPEG frames and (for Whisper / multimodal audio mode) a mono 16 kHz audio clip
- Sends extracted audio to Groq (`api.groq.com`) when `GROQ_API_KEY` is set
- Sends extracted audio to OpenAI (`api.openai.com`) when `OPENAI_API_KEY` is set and Groq isn't, or when `--whisper openai` is forced
- Sends video (≤ 2 min) or audio to the multimodal endpoint (default `integrate.api.nvidia.com`) when `MULTIMODAL_API_KEY` is set and multimodal is triggered
- Writes downloaded video, frames, audio, and an intermediate transcript to a working directory under the system temp dir (or `--out-dir`)
- Reads/creates `~/.config/watch/.env` (mode `0600`) for keys and a `SETUP_COMPLETE` marker; falls back to `.env` in the cwd

## What the skill does NOT do

- Does not upload the video to Whisper APIs — only extracted audio. Video uploads only go to the multimodal endpoint, only in video mode (≤ 2 min)
- Does not access platform accounts (no login, no cookies, no posting)
- Does not share keys between providers (Groq → groq.com, OpenAI → openai.com, multimodal → its configured base URL)
- Does not log, cache, or write API keys to stdout, stderr, or output files
- Does not persist anything outside the working directory and `~/.config/watch/.env`

## Bundled scripts

`scripts/watch.py` (entry point), `download.py` (yt-dlp wrapper), `frames.py` (ffmpeg + auto-fps), `transcribe.py` (caption selection + Whisper orchestration), `whisper.py` (Groq/OpenAI clients, stdlib only), `multimodal.py` (provider-agnostic multimodal client), `setup.py` (preflight + installer).

Review before first use to verify behavior.
