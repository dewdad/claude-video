#!/usr/bin/env python3
"""Multimodal media analysis via OpenAI-compatible chat/completions API.

Provider-agnostic: works with any endpoint that accepts the OpenAI multimodal
message format (video_url / input_audio content types). Configurable via
environment variables with strong defaults pointing to NVIDIA NIM (Nemotron).

Configuration (env or ~/.config/watch/.env):
  MULTIMODAL_API_KEY    — Required. API key for the provider.
  MULTIMODAL_BASE_URL   — Endpoint URL. Default: https://integrate.api.nvidia.com/v1
  MULTIMODAL_MODEL      — Model identifier. Default: nvidia/nemotron-3-nano-omni-30b-a3b-reasoning
  MULTIMODAL_MAX_TOKENS — Max output tokens. Default: 4096

Legacy compat: NGC_API_KEY is accepted as fallback for MULTIMODAL_API_KEY.

Pure stdlib — no pip dependencies.
"""
from __future__ import annotations

import base64
import json
import os
import ssl
import sys
import time
import urllib.error
from pathlib import Path
from urllib.request import Request, urlopen


DEFAULT_BASE_URL = "https://integrate.api.nvidia.com/v1"
DEFAULT_MODEL = "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning"
DEFAULT_MAX_TOKENS = 4096

MAX_VIDEO_DURATION_SEC = 120
MAX_AUDIO_DURATION_SEC = 3600

MAX_ATTEMPTS = 3
RETRY_BASE_DELAY = 3.0

DOTENV_PATHS = [
    Path.home() / ".config" / "watch" / ".env",
    Path.cwd() / ".env",
]


def _read_dotenv_key(name: str) -> str | None:
    for path in DOTENV_PATHS:
        if not path.exists():
            continue
        try:
            for line in path.read_text().splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, raw = line.partition("=")
                if key.strip() != name:
                    continue
                raw = raw.strip()
                if len(raw) >= 2 and raw[0] in ('"', "'") and raw[-1] == raw[0]:
                    raw = raw[1:-1]
                return raw or None
        except OSError:
            continue
    return None


def _resolve_env(name: str, fallback_names: list[str] | None = None) -> str | None:
    value = os.environ.get(name)
    if value and value.strip():
        return value.strip()
    result = _read_dotenv_key(name)
    if result:
        return result
    for fb in fallback_names or []:
        value = os.environ.get(fb)
        if value and value.strip():
            return value.strip()
        result = _read_dotenv_key(fb)
        if result:
            return result
    return None


def load_config(
    *,
    api_key: str | None = None,
    base_url: str | None = None,
    model: str | None = None,
) -> dict:
    """Resolve multimodal provider configuration.

    Priority: explicit args > env vars > .env file > defaults.
    Returns dict with keys: api_key, base_url, model, max_tokens.
    """
    resolved_key = api_key or _resolve_env("MULTIMODAL_API_KEY", ["NGC_API_KEY"])
    resolved_url = base_url or _resolve_env("MULTIMODAL_BASE_URL") or DEFAULT_BASE_URL
    resolved_model = model or _resolve_env("MULTIMODAL_MODEL") or DEFAULT_MODEL
    resolved_max_tokens = int(_resolve_env("MULTIMODAL_MAX_TOKENS") or DEFAULT_MAX_TOKENS)

    if resolved_url.endswith("/"):
        resolved_url = resolved_url.rstrip("/")

    return {
        "api_key": resolved_key,
        "base_url": resolved_url,
        "model": resolved_model,
        "max_tokens": resolved_max_tokens,
    }


def has_multimodal_key() -> bool:
    return bool(_resolve_env("MULTIMODAL_API_KEY", ["NGC_API_KEY"]))


def _encode_file_b64(file_path: Path) -> str:
    return base64.b64encode(file_path.read_bytes()).decode("utf-8")


def _detect_media_type(file_path: Path) -> tuple[str, str]:
    ext = file_path.suffix.lower()
    video_types = {
        ".mp4": "video/mp4",
        ".mov": "video/quicktime",
        ".webm": "video/webm",
        ".mkv": "video/x-matroska",
    }
    audio_types = {
        ".mp3": "audio/mpeg",
        ".wav": "audio/wav",
        ".ogg": "audio/ogg",
        ".flac": "audio/flac",
        ".m4a": "audio/mp4",
        ".aac": "audio/aac",
    }
    if ext in video_types:
        return "video", video_types[ext]
    if ext in audio_types:
        return "audio", audio_types[ext]
    return "video", "video/mp4"


def _build_request_body(
    file_path: Path,
    prompt: str,
    config: dict,
    *,
    use_audio_in_video: bool = True,
) -> dict:
    category, mime_type = _detect_media_type(file_path)
    b64_data = _encode_file_b64(file_path)
    data_url = f"data:{mime_type};base64,{b64_data}"

    if category == "video":
        content_item = {
            "type": "video_url",
            "video_url": {"url": data_url},
        }
    else:
        content_item = {
            "type": "input_audio",
            "input_audio": {"data": b64_data, "format": file_path.suffix.lstrip(".")},
        }

    body: dict = {
        "model": config["model"],
        "messages": [
            {
                "role": "user",
                "content": [
                    content_item,
                    {"type": "text", "text": prompt},
                ],
            }
        ],
        "max_tokens": config["max_tokens"],
        "temperature": 0,
        "stream": False,
    }

    # NVIDIA NIM-specific fields — included when targeting the default provider
    if "nvidia.com" in config["base_url"]:
        body["extra_body"] = {
            "chat_template_kwargs": {"enable_thinking": False},
            "mm_processor_kwargs": {"use_audio_in_video": use_audio_in_video},
        }

    return body


def _post_completions(config: dict, body: dict) -> dict:
    endpoint = f"{config['base_url']}/chat/completions"
    data = json.dumps(body).encode("utf-8")
    headers = {
        "Authorization": f"Bearer {config['api_key']}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "watch-skill/1.0 (+claude-video; python-urllib)",
    }

    if "nvidia.com" in config["base_url"]:
        headers["NVCF-POLL-SECONDS"] = "300"

    context = ssl.create_default_context()
    last_exc: Exception | None = None

    for attempt in range(MAX_ATTEMPTS):
        request = Request(endpoint, data=data, headers=headers, method="POST")
        try:
            with urlopen(request, timeout=600, context=context) as response:
                payload = response.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            last_exc = exc
            detail = ""
            try:
                detail = f" — {exc.read().decode('utf-8', errors='replace')[:400]}"
            except Exception:
                pass

            if 400 <= exc.code < 500 and exc.code != 429:
                raise SystemExit(
                    f"Multimodal API error ({exc.code}): {exc}{detail}"
                )

            delay = RETRY_BASE_DELAY * (2 ** attempt) + (2 if exc.code == 429 else 0)

            if attempt < MAX_ATTEMPTS - 1:
                print(
                    f"[watch] multimodal HTTP {exc.code} — retrying in {delay:.1f}s "
                    f"(attempt {attempt + 2}/{MAX_ATTEMPTS})",
                    file=sys.stderr,
                )
                time.sleep(delay)
            continue
        except (urllib.error.URLError, TimeoutError, ConnectionResetError, OSError) as exc:
            last_exc = exc
            if attempt < MAX_ATTEMPTS - 1:
                delay = RETRY_BASE_DELAY * (attempt + 1)
                print(
                    f"[watch] multimodal network error ({type(exc).__name__}) — "
                    f"retrying in {delay:.1f}s (attempt {attempt + 2}/{MAX_ATTEMPTS})",
                    file=sys.stderr,
                )
                time.sleep(delay)
            continue

        try:
            return json.loads(payload)
        except json.JSONDecodeError as exc:
            raise SystemExit(f"Multimodal API returned non-JSON: {exc}: {payload[:200]}")

    raise SystemExit(f"Multimodal request failed after {MAX_ATTEMPTS} attempts: {last_exc}")


def _extract_text(response: dict) -> str:
    choices = response.get("choices") or []
    if not choices:
        raise SystemExit("Multimodal API returned no choices")
    message = choices[0].get("message") or {}
    content = message.get("content") or ""
    if not content.strip():
        raise SystemExit("Multimodal API returned empty content")
    return content.strip()


def analyze_video(
    video_path: Path,
    duration_seconds: float,
    config: dict,
    *,
    prompt: str | None = None,
) -> str:
    if duration_seconds > MAX_VIDEO_DURATION_SEC:
        raise SystemExit(
            f"Video is {duration_seconds:.0f}s — exceeds {MAX_VIDEO_DURATION_SEC}s "
            f"limit for video input. Use --multimodal-audio for audio-only analysis."
        )

    file_size = video_path.stat().st_size
    if file_size > 180 * 1024 * 1024:
        raise SystemExit(
            f"Video file is {file_size / (1024*1024):.0f} MB — too large for inline upload. "
            "Consider trimming the video or using --start/--end."
        )

    if prompt is None:
        prompt = (
            "Analyze this video comprehensively. Provide:\n"
            "1. A timestamped description of what happens visually\n"
            "2. What is heard in the audio (speech transcription, music, sound effects, ambient sounds)\n"
            "3. How audio and visual elements relate to each other\n"
            "4. Any on-screen text or graphics\n\n"
            "Format timestamps as [MM:SS] or [HH:MM:SS]. Be specific and detailed."
        )

    model_label = config["model"].split("/")[-1] if "/" in config["model"] else config["model"]
    print(
        f"[watch] sending video ({file_size / 1024:.0f} kB, {duration_seconds:.0f}s) "
        f"to {model_label}…",
        file=sys.stderr,
    )

    body = _build_request_body(video_path, prompt, config, use_audio_in_video=True)
    response = _post_completions(config, body)
    return _extract_text(response)


def analyze_audio(
    audio_path: Path,
    config: dict,
    *,
    prompt: str | None = None,
) -> str:
    file_size = audio_path.stat().st_size
    if file_size > 100 * 1024 * 1024:
        raise SystemExit(
            f"Audio file is {file_size / (1024*1024):.0f} MB — may exceed API limits. "
            "Consider trimming."
        )

    if prompt is None:
        prompt = (
            "Analyze this audio comprehensively. Provide:\n"
            "1. Transcription of any speech with timestamps [MM:SS]\n"
            "2. Description of non-speech audio (music genre/mood, instruments, "
            "sound effects, ambient sounds)\n"
            "3. Speaker identification if multiple speakers\n"
            "4. Notable audio events or transitions\n\n"
            "Be specific and detailed. Use timestamps where possible."
        )

    model_label = config["model"].split("/")[-1] if "/" in config["model"] else config["model"]
    print(
        f"[watch] sending audio ({file_size / 1024:.0f} kB) to {model_label}…",
        file=sys.stderr,
    )

    body = _build_request_body(audio_path, prompt, config, use_audio_in_video=False)
    response = _post_completions(config, body)
    return _extract_text(response)


def analyze_media(
    file_path: Path,
    duration_seconds: float,
    config: dict,
    *,
    mode: str = "auto",
    prompt: str | None = None,
) -> tuple[str, str]:
    category, _ = _detect_media_type(file_path)

    if mode == "auto":
        if category == "audio":
            mode = "audio"
        elif duration_seconds <= MAX_VIDEO_DURATION_SEC:
            mode = "video"
        else:
            mode = "audio"

    if mode == "video":
        text = analyze_video(file_path, duration_seconds, config, prompt=prompt)
        return text, "video"
    else:
        text = analyze_audio(file_path, config, prompt=prompt)
        return text, "audio"


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(
            "usage: multimodal.py <media-path> [--mode video|audio|auto] [--prompt '...'] "
            "[--model MODEL] [--base-url URL]",
            file=sys.stderr,
        )
        raise SystemExit(2)

    media_path = Path(sys.argv[1])
    if not media_path.exists():
        raise SystemExit(f"File not found: {media_path}")

    mode = "auto"
    prompt = None
    cli_model = None
    cli_base_url = None
    if "--mode" in sys.argv:
        mode = sys.argv[sys.argv.index("--mode") + 1]
    if "--prompt" in sys.argv:
        prompt = sys.argv[sys.argv.index("--prompt") + 1]
    if "--model" in sys.argv:
        cli_model = sys.argv[sys.argv.index("--model") + 1]
    if "--base-url" in sys.argv:
        cli_base_url = sys.argv[sys.argv.index("--base-url") + 1]

    cfg = load_config(model=cli_model, base_url=cli_base_url)
    if not cfg["api_key"]:
        raise SystemExit(
            "MULTIMODAL_API_KEY (or NGC_API_KEY) not found. "
            "Set in env or ~/.config/watch/.env"
        )

    result, used_mode = analyze_media(media_path, 0, cfg, mode=mode, prompt=prompt)
    print(f"[multimodal] provider: {cfg['base_url']}")
    print(f"[multimodal] model: {cfg['model']}")
    print(f"[multimodal] mode: {used_mode}")
    print(result)
