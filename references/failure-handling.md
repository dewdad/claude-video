# Failure handling

| Symptom | Cause | Action |
|---------|-------|--------|
| Preflight non-zero exit | Missing deps or key | Run `python3 "$SKILL_DIR/scripts/setup.py"`, then `AskUserQuestion` for key if needed |
| "No transcript available" in report | All backends unavailable or failed | Proceed frames-only; tell user; offer to add a key |
| Long-video warning printed | > 10 min, sparse scan | Acknowledge in answer; offer `--start`/`--end` re-run on the relevant section |
| yt-dlp download error (stderr) | Login-required, region-locked, removed | Tell user plainly; do not retry |
| Whisper request error | Bad key, rate limit, > 25 MB upload (very long audio) | Retry with `--whisper openai` if Groq failed (or vice versa); or `--multimodal-audio` |
| Multimodal request error | Bad key, video > 2 min in video mode, rate limit | Try `--multimodal-audio` (longer support), swap `--multimodal-base-url`, or `--no-multimodal` |

## Setup exit codes

| Exit | Meaning |
|------|---------|
| 0 | Ready |
| 2 | Missing binaries (`ffmpeg` / `ffprobe` / `yt-dlp`) |
| 3 | No Whisper / multimodal API key |
| 4 | Both binaries and key missing |

## Setup `--json` schema

`python3 "$SKILL_DIR/scripts/setup.py" --json` returns:

```
{
  "status": "ready" | "needs_install" | "needs_key" | "needs_install_and_key",
  "first_run": bool,
  "missing_binaries": [str],
  "whisper_backend": "groq" | "openai" | null,
  "has_api_key": bool,
  "has_ngc_key": bool,
  "nemotron_available": bool,
  "config_file": str,
  "platform": str
}
```

Use when you need to branch on first-run state or specific missing pieces.
