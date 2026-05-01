---
name: watch
description: Watch a video (URL or local path). Downloads with yt-dlp, extracts auto-scaled frames with ffmpeg, pulls the transcript from captions (or Whisper API fallback), and hands the result to the agent so it can answer questions about what's in the video.
argument-hint: "<video-url-or-path> [question]"
allowed-tools: Bash, Read, AskUserQuestion
homepage: https://github.com/dewdad/claude-video
repository: https://github.com/dewdad/claude-video
author: bradautomates
license: MIT
user-invocable: true
---

# /watch — Watch a video

You don't have a video input; this skill gives you one. A Python script downloads the video, extracts frames as JPEGs, gets a timestamped transcript (native captions first, then Whisper API as fallback), and prints frame paths. You then `Read` each frame path to see the images and combine them with the transcript to answer the user.

**Skill directory variable:** Throughout this document, `$SKILL_DIR` refers to the directory containing this SKILL.md file and the `scripts/` subdirectory. Depending on your tool:
- **OpenCode**: `$SKILL_DIR` is resolved automatically to the skill's install path (e.g. `~/.config/opencode/skills/watch`)
- **Claude Code**: Use `$CLAUDE_SKILL_DIR` (or `$CLAUDE_PLUGIN_ROOT`)
- **Other tools**: The directory containing this file

## Step 0 — Setup preflight (runs every `/watch` invocation, silent on success)

**Python interpreter:** every `python3 ...` command in this skill is for macOS/Linux. On **Windows**, substitute `python` — the `python3` command on Windows is the Microsoft Store stub and will not run the script.

Before every `/watch` run, verify that dependencies and an API key are in place:

```bash
python3 "$SKILL_DIR/scripts/setup.py" --check
```

This is a <100ms lookup. On exit 0, the script emits **nothing** — proceed to Step 1 without comment. **Do NOT announce "setup is complete" to the user** — they don't need a status message on every turn. The only acceptable user-visible output from Step 0 is when remediation is required.

On non-zero exit, follow the table:

| Exit | Meaning | Action |
|------|---------|--------|
| `2` | Missing binaries (`ffmpeg` / `ffprobe` / `yt-dlp`) | Run installer |
| `3` | No Whisper API key | Run installer to scaffold `.env`, then ask user for a key |
| `4` | Both missing | Run installer, then ask for a key |

The installer is idempotent — safe to re-run:

```bash
python3 "$SKILL_DIR/scripts/setup.py"
```

On macOS with Homebrew, it auto-installs `ffmpeg` and `yt-dlp`. On Linux/Windows, it prints the exact install commands for the user to run. It scaffolds `~/.config/watch/.env` with commented placeholders at `0600` perms, and writes `SETUP_COMPLETE=true` once deps + a key are in place so the next session knows this user has already been through the wizard.

**If an API key is still missing after install:** use `AskUserQuestion` to ask the user whether they have a Groq API key (preferred — cheaper, faster), an OpenAI key, or a multimodal provider key (default: NVIDIA NGC for Nemotron). Then write it into `~/.config/watch/.env` — set the matching `GROQ_API_KEY=...`, `OPENAI_API_KEY=...`, or `MULTIMODAL_API_KEY=...` line. If they don't want to set up any transcription backend, proceed with `--no-whisper --no-multimodal` and tell them videos without native captions will come back frames-only.

**Structured mode (optional):** `python3 "$SKILL_DIR/scripts/setup.py" --json` emits `{status, first_run, missing_binaries, whisper_backend, has_api_key, has_ngc_key, nemotron_available, config_file, platform}` where `status` is one of `ready | needs_install | needs_key | needs_install_and_key`. Use this when you need to branch on specifics (e.g. "is this the user's very first run?" → `first_run: true`).

Within a single session, you can skip Step 0 on follow-up `/watch` calls — once `--check` returned 0, nothing about the environment changes between turns.

## When to use

- User pastes a video URL (YouTube, Vimeo, X, TikTok, Twitch clip, most yt-dlp-supported sites) and asks about it.
- User points at a local video file (`.mp4`, `.mov`, `.mkv`, `.webm`, etc.) and asks about it.
- User types `/watch <url-or-path> [question]`.

## Recommended limits

- **Best accuracy: videos under 10 minutes.** Frame coverage scales inversely with duration.
- **Hard caps: 100 frames total and 2 fps.** Token cost grows with frame count, so the script targets a frame budget by duration (and never exceeds 2 fps even when the budget would imply more):
  - ≤30s → ~1-2 fps (up to 30 frames)
  - 30s-1min → ~40 frames
  - 1-3min → ~60 frames
  - 3-10min → ~80 frames
  - \>10min → 100 frames, sparsely spaced (warning printed)
- If the user hands you a long video, consider asking whether they want a specific section before burning tokens on a sparse scan.

## How to invoke

**Step 1 — parse the user input.** Separate the video source (URL or path) from any question the user asked. Example: `/watch https://youtu.be/abc what language is this in?` → source = `https://youtu.be/abc`, question = `what language is this in?`.

**Step 2 — run the watch script.** Pass the source verbatim. Do not shell-escape it yourself beyond normal quoting:

```bash
python3 "$SKILL_DIR/scripts/watch.py" "<source>"
```

Optional flags:
- `--start T` / `--end T` — focus on a section. Accepts `SS`, `MM:SS`, or `HH:MM:SS`. When either is set, fps auto-scales denser (see "Focusing on a section" below).
- `--max-frames N` — lower the cap for tighter token budget (e.g. `--max-frames 40`)
- `--resolution W` — change frame width in px (default 512; bump to 1024 only if the user needs to read on-screen text)
- `--fps F` — override auto-fps (clamped to 2 fps max)
- `--out-dir DIR` — keep working files somewhere specific (default: an auto-generated tmp dir)
- `--whisper groq|openai` — force a specific Whisper backend (default: prefer Groq if both keys exist)
- `--no-whisper` — disable the Whisper fallback entirely (frames-only if no captions)
- `--multimodal` — use multimodal analysis (video ≤2 min, or auto-falls back to audio mode for longer). Provides unified audio+visual understanding including non-speech audio (music, SFX, ambient). Requires `MULTIMODAL_API_KEY`.
- `--multimodal-audio` — force multimodal audio-only mode (up to 1 hr). Use for long videos when you want non-speech audio analysis or when Whisper is unavailable.
- `--no-multimodal` — disable multimodal fallback even when `MULTIMODAL_API_KEY` is available.
- `--multimodal-model MODEL` — override the model (default: env `MULTIMODAL_MODEL` or `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning`).
- `--multimodal-base-url URL` — override the API endpoint (default: env `MULTIMODAL_BASE_URL` or `https://integrate.api.nvidia.com/v1`). Use to swap providers (OpenRouter, local vLLM, etc.).

### Focusing on a section (higher frame rate)

When the user asks about a specific moment — "what happens at the 2 minute mark?", "zoom into 0:45 to 1:00", "the first 10 seconds" — pass `--start` and/or `--end`. The script switches to focused-mode budgets, which are denser than full-video budgets (still capped at 2 fps):

- ≤5s → 2 fps (up to 10 frames)
- 5-15s → 2 fps (up to 30 frames)
- 15-30s → ~2 fps (up to 60 frames)
- 30-60s → ~1.3 fps (up to 80 frames)
- 60-180s → ~0.6 fps (100 frames, capped)

Focused mode is the right call for:
- Any moment/range the user names explicitly ("around 2:30", "the intro", "the last 30 seconds").
- Any video longer than ~10 minutes where the user's question is about a specific part — running focused on the relevant section is far more useful than a sparse scan of the whole thing.
- Re-runs after a full scan didn't have enough detail in some region.

Transcript is auto-filtered to the same range. Frame timestamps are absolute (real video timeline, not offset-from-start).

Examples:
```bash
# Last 10 seconds of a 1 minute video
python3 "$SKILL_DIR/scripts/watch.py" video.mp4 --start 50 --end 60

# Zoom into 2:15 → 2:45 at 3 fps (90 frames)
python3 "$SKILL_DIR/scripts/watch.py" "$URL" --start 2:15 --end 2:45 --fps 3

# From 1h12m to the end of the video
python3 "$SKILL_DIR/scripts/watch.py" "$URL" --start 1:12:00
```

**Step 3 — Read every frame path the script lists.** The Read tool renders JPEGs directly as images for you. Read all frames in a single message (parallel tool calls) so you see them together. The frames are in chronological order with a `t=MM:SS` timestamp so you can align them to the transcript.

**Step 4 — answer the user.** You now have two streams of evidence:
- **Frames** — what's on screen at each timestamp
- **Transcript** — what's said at each timestamp. The report's header shows the source (`captions` = yt-dlp pulled native subs; `whisper (groq)` or `whisper (openai)` = transcribed by API).

If the user asked a specific question, answer it directly citing timestamps. If they didn't ask anything, summarize what happens in the video — structure, key moments, notable visuals, spoken content.

**Step 5 — clean up.** The script prints a working directory at the end. If the user isn't going to ask follow-ups about this video, delete it with `rm -rf <dir>`. If they might, leave it in place.

## Transcription

The script gets a timestamped transcript via a priority chain:

1. **Native captions (free, preferred).** yt-dlp pulls manual or auto-generated subtitles from the source platform if available.
2. **Whisper API fallback.** If no captions came back (or the source is a local file), the script extracts audio (`ffmpeg -vn -ac 1 -ar 16000 -b:a 64k`, ~0.5 MB/min) and uploads it to whichever Whisper API has a key configured:
   - **Groq** — `whisper-large-v3`. Preferred default: cheaper, faster. Get a key at console.groq.com/keys.
   - **OpenAI** — `whisper-1`. Fallback. Get a key at platform.openai.com/api-keys.
3. **Multimodal fallback.** If both captions and Whisper are unavailable (or explicitly via `--multimodal`), the script sends the media to a multimodal model for unified audio-visual analysis:
   - **Video mode** (≤2 min) — sends the full video for joint audio+visual understanding.
   - **Audio mode** (≤1 hr) — extracts and sends audio only. Used automatically for videos >2 min or when `--multimodal-audio` is set.
   - **Advantages over Whisper:** understands non-speech audio (music, sound effects, ambient), correlates audio with visuals, identifies speakers from visual context.
   - **Limitation:** reasoning is disabled for media inputs on NVIDIA NIM — the model describes/transcribes but cannot do deep analytical reasoning. The agent (you) does the reasoning.
   - **Provider-agnostic:** works with any OpenAI-compatible multimodal endpoint. Default: NVIDIA NIM (Nemotron-3-Nano-Omni).
   - Configure via `~/.config/watch/.env`:
     - `MULTIMODAL_API_KEY` — required (or legacy `NGC_API_KEY`)
     - `MULTIMODAL_BASE_URL` — default: `https://integrate.api.nvidia.com/v1`
     - `MULTIMODAL_MODEL` — default: `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning`

All keys live in `~/.config/watch/.env`. The priority chain is: captions → Whisper → multimodal. Override with `--multimodal` to use multimodal directly, or `--no-multimodal` to skip it.

## Failure modes and handling

- **Setup preflight failed** → run `python3 "$SKILL_DIR/scripts/setup.py"` (auto-installs ffmpeg/yt-dlp via brew on macOS, scaffolds the `.env`). For API key, ask the user via `AskUserQuestion` and write it to `~/.config/watch/.env`.
- **No transcript available** → captions missing AND (no Whisper key OR Whisper API failed) AND (no multimodal key OR multimodal failed). Script prints a hint pointing to setup. Proceed frames-only and tell the user.
- **Long video warning printed** → acknowledge it in your answer. Offer to re-run focused on a specific section via `--start`/`--end` rather than a sparse full-video scan.
- **Download fails** → yt-dlp's error goes to stderr. If it's a login-required or region-locked video, tell the user plainly; do not keep retrying.
- **Whisper request fails** → the error is printed to stderr (likely: invalid key, rate limit, or 25 MB upload limit on a very long video). The report will say "none available" for transcript. You can retry with `--whisper openai` if Groq failed (or vice versa).
- **Multimodal request fails** → the error is printed to stderr (likely: invalid API key, video >2 min in video mode, rate limit). Try `--multimodal-audio` for longer content, `--multimodal-base-url` to switch providers, or fall back to Whisper with `--no-multimodal`.

## Token efficiency

This skill burns tokens primarily on frames. Order of magnitude:
- 80 frames at 512px wide is roughly 50-80k image tokens depending on aspect ratio.
- The transcript is cheap (a few thousand tokens at most for a 10-minute video).
- Bumping `--resolution` to 1024 roughly quadruples the image tokens per frame. Only do it when necessary.

If you already watched a video this session and the user asks a follow-up, do **not** re-run the script — you already have the frames and transcript in context. Just answer from what you have.

## Security & Permissions

**What this skill does:**
- Runs `yt-dlp` locally to download the video and pull native captions when the source supports them (public data; the request goes directly to whatever host the URL points at)
- Runs `ffmpeg` / `ffprobe` locally to extract frames as JPEGs and, when Whisper or Nemotron audio mode is needed, a mono 16 kHz audio clip
- Sends the extracted audio clip to Groq's Whisper API (`api.groq.com/openai/v1/audio/transcriptions`) when `GROQ_API_KEY` is set (preferred — cheaper, faster)
- Sends the extracted audio clip to OpenAI's audio transcription API (`api.openai.com/v1/audio/transcriptions`) when `OPENAI_API_KEY` is set and Groq is not, or when `--whisper openai` is forced
- Sends the video file (≤2 min) or extracted audio to the configured multimodal endpoint (default: `integrate.api.nvidia.com/v1/chat/completions`) when `MULTIMODAL_API_KEY` is set and multimodal is triggered (as fallback or via `--multimodal`)
- Writes the downloaded video, frames, audio, and an intermediate transcript to a working directory under the system temp dir (or `--out-dir` if specified) so the agent can `Read` them
- Reads / creates `~/.config/watch/.env` (mode `0600`) to store API key(s) and a `SETUP_COMPLETE` marker. As a fallback, also reads `.env` in the current working directory

**What this skill does NOT do:**
- Does not upload the video itself to Whisper APIs — only the extracted audio goes to Groq/OpenAI. Video uploads only go to NVIDIA NIM when Nemotron video mode is active (≤2 min videos).
- Does not access any platform account (no login, no session cookies, no posting)
- Does not share API keys between providers (Groq key → `api.groq.com`, OpenAI key → `api.openai.com`, NGC key → `integrate.api.nvidia.com`)
- Does not log, cache, or write API keys to stdout, stderr, or output files
- Does not persist anything outside the working directory and `~/.config/watch/.env` — clean up the working directory when you're done (Step 5)

**Bundled scripts:** `scripts/watch.py` (entry point), `scripts/download.py` (yt-dlp wrapper), `scripts/frames.py` (ffmpeg frame extraction), `scripts/transcribe.py` (caption selection + Whisper orchestration), `scripts/whisper.py` (Groq / OpenAI clients), `scripts/multimodal.py` (provider-agnostic multimodal client; default: NVIDIA NIM), `scripts/setup.py` (preflight + installer)

Review scripts before first use to verify behavior.
