#!/usr/bin/env python3
"""/watch entry point: download video, extract frames, parse transcript.

Prints a markdown report to stdout listing frame paths + transcript. The agent
then Reads each frame path to see the video.
"""
from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path


SCRIPT_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(SCRIPT_DIR))

from download import download, is_url  # noqa: E402
from frames import MAX_FPS, auto_fps, auto_fps_focus, extract, format_time, get_metadata, parse_time  # noqa: E402
from multimodal import analyze_media, has_multimodal_key, load_config, MAX_VIDEO_DURATION_SEC  # noqa: E402
from transcribe import filter_range, format_transcript, parse_vtt  # noqa: E402
from whisper import extract_audio, load_api_key, transcribe_video  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(
        prog="watch",
        description="Download a video, extract auto-scaled frames, and surface the transcript.",
    )
    ap.add_argument("source", help="Video URL or local file path")
    ap.add_argument("--max-frames", type=int, default=80, help="Cap on frame count (default 80, hard max 100)")
    ap.add_argument("--resolution", type=int, default=512, help="Frame width in pixels (default 512)")
    ap.add_argument("--fps", type=float, default=None, help="Override auto-fps")
    ap.add_argument("--start", type=str, default=None, help="Range start (SS, MM:SS, or HH:MM:SS)")
    ap.add_argument("--end", type=str, default=None, help="Range end (SS, MM:SS, or HH:MM:SS)")
    ap.add_argument("--out-dir", type=str, default=None, help="Working directory (default: tmp)")
    ap.add_argument(
        "--no-whisper",
        action="store_true",
        help="Disable Whisper fallback. Report frames-only if no captions available.",
    )
    ap.add_argument(
        "--whisper",
        choices=["groq", "openai"],
        default=None,
        help="Force a specific Whisper backend. Default: prefer Groq, fall back to OpenAI.",
    )
    ap.add_argument(
        "--multimodal",
        action="store_true",
        help="Use multimodal analysis (video ≤2min or audio). "
             "Provides unified audio+visual understanding including non-speech audio.",
    )
    ap.add_argument(
        "--multimodal-audio",
        action="store_true",
        help="Force multimodal audio-only mode (up to 1hr). Use for long videos or "
             "when you want non-speech audio analysis (music, SFX, ambient sounds).",
    )
    ap.add_argument(
        "--no-multimodal",
        action="store_true",
        help="Disable multimodal fallback even when MULTIMODAL_API_KEY is available.",
    )
    ap.add_argument(
        "--multimodal-model",
        type=str,
        default=None,
        help="Override multimodal model (default: from env or nvidia/nemotron-3-nano-omni-30b-a3b-reasoning).",
    )
    ap.add_argument(
        "--multimodal-base-url",
        type=str,
        default=None,
        help="Override multimodal API base URL (default: from env or https://integrate.api.nvidia.com/v1).",
    )
    args = ap.parse_args()

    max_frames = min(args.max_frames, 100)

    if args.out_dir:
        work = Path(args.out_dir).expanduser().resolve()
    else:
        work = Path(tempfile.mkdtemp(prefix="watch-"))
    work.mkdir(parents=True, exist_ok=True)
    print(f"[watch] working dir: {work}", file=sys.stderr)

    print(
        "[watch] downloading via yt-dlp…" if is_url(args.source) else "[watch] using local file…",
        file=sys.stderr,
    )
    dl = download(args.source, work / "download")
    video_path = dl["video_path"]

    meta = get_metadata(video_path)
    full_duration = meta["duration_seconds"]

    start_sec = parse_time(args.start)
    end_sec = parse_time(args.end)

    if start_sec is not None and start_sec < 0:
        raise SystemExit("--start must be non-negative")
    if end_sec is not None and start_sec is not None and end_sec <= start_sec:
        raise SystemExit("--end must be greater than --start")
    if full_duration > 0 and start_sec is not None and start_sec >= full_duration:
        raise SystemExit(f"--start {start_sec:.1f}s is past end of video ({full_duration:.1f}s)")

    effective_start = start_sec if start_sec is not None else 0.0
    effective_end = end_sec if end_sec is not None else full_duration
    effective_duration = max(0.0, effective_end - effective_start)
    focused = start_sec is not None or end_sec is not None

    if focused:
        fps, target = auto_fps_focus(effective_duration, max_frames=max_frames)
    else:
        fps, target = auto_fps(effective_duration, max_frames=max_frames)
    if args.fps is not None:
        fps = min(args.fps, MAX_FPS)
        target = max(1, int(round(fps * effective_duration)))

    scope = (
        f"{format_time(effective_start)}-{format_time(effective_end)} ({effective_duration:.1f}s)"
        if focused else f"full {effective_duration:.1f}s"
    )
    print(f"[watch] extracting ~{target} frames at {fps:.3f} fps over {scope}…", file=sys.stderr)

    frames = extract(
        video_path,
        work / "frames",
        fps=fps,
        resolution=args.resolution,
        max_frames=max_frames,
        start_seconds=start_sec,
        end_seconds=end_sec,
    )

    transcript_segments: list[dict] = []
    transcript_text: str | None = None
    transcript_source: str | None = None
    nemotron_analysis: str | None = None

    # --- Multimodal: explicit --multimodal or --multimodal-audio overrides the pipeline ---
    if args.multimodal or args.multimodal_audio:
        mm_config = load_config(
            model=args.multimodal_model,
            base_url=args.multimodal_base_url,
        )
        if mm_config["api_key"]:
            mode = "audio" if args.multimodal_audio else "auto"
            try:
                if mode == "audio":
                    audio_out = work / "multimodal-audio.mp3"
                    extract_audio(video_path, audio_out)
                    media_path = audio_out
                else:
                    media_path = Path(video_path)
                text, used_mode = analyze_media(
                    media_path, full_duration, mm_config, mode=mode,
                )
                nemotron_analysis = text
                transcript_source = f"multimodal ({used_mode})"
            except SystemExit as exc:
                print(f"[watch] multimodal failed: {exc}", file=sys.stderr)
        else:
            print(
                "[watch] --multimodal requested but MULTIMODAL_API_KEY (or NGC_API_KEY) not found. "
                "Set it in ~/.config/watch/.env or environment.",
                file=sys.stderr,
            )

    # --- Standard pipeline: captions → whisper → nemotron fallback ---
    if not nemotron_analysis:
        if dl.get("subtitle_path"):
            try:
                all_segments = parse_vtt(dl["subtitle_path"])
                transcript_segments = filter_range(all_segments, start_sec, end_sec) if focused else all_segments
                transcript_text = format_transcript(transcript_segments)
                transcript_source = "captions"
            except Exception as exc:
                print(f"[watch] subtitle parse failed: {exc}", file=sys.stderr)

        if not transcript_segments and not args.no_whisper:
            backend, api_key = load_api_key(args.whisper)
            if backend and api_key:
                try:
                    all_segments, used_backend = transcribe_video(
                        video_path,
                        work / "audio.mp3",
                        backend=backend,
                        api_key=api_key,
                    )
                    transcript_segments = filter_range(all_segments, start_sec, end_sec) if focused else all_segments
                    transcript_text = format_transcript(transcript_segments)
                    transcript_source = f"whisper ({used_backend})"
                except SystemExit as exc:
                    print(f"[watch] whisper fallback failed: {exc}", file=sys.stderr)
            else:
                hint = (
                    f"--whisper {args.whisper} was set but the matching API key is missing"
                    if args.whisper else
                    "no subtitles and no Whisper API key found"
                )
                setup_py = SCRIPT_DIR / "setup.py"
                print(
                    f"[watch] {hint} — run `python3 {setup_py}` to enable the Whisper fallback",
                    file=sys.stderr,
                )

        # --- Multimodal auto-fallback: if no transcript yet and key available ---
        if not transcript_segments and not args.no_multimodal and not nemotron_analysis:
            if has_multimodal_key():
                mm_config = load_config(
                    model=args.multimodal_model,
                    base_url=args.multimodal_base_url,
                )
                mode = "audio" if full_duration > MAX_VIDEO_DURATION_SEC else "auto"
                try:
                    if mode == "audio":
                        audio_out = work / "multimodal-audio.mp3"
                        extract_audio(video_path, audio_out)
                        media_file = audio_out
                    else:
                        media_file = Path(video_path)
                    text, used_mode = analyze_media(
                        media_file, full_duration, mm_config, mode=mode,
                    )
                    nemotron_analysis = text
                    transcript_source = f"multimodal ({used_mode})"
                except SystemExit as exc:
                    print(f"[watch] multimodal fallback failed: {exc}", file=sys.stderr)

    info = dl.get("info") or {}

    print()
    print("# watch: video report")
    print()
    print(f"- **Source:** {args.source}")
    if info.get("title"):
        print(f"- **Title:** {info['title']}")
    if info.get("uploader"):
        print(f"- **Uploader:** {info['uploader']}")
    print(f"- **Duration:** {format_time(full_duration)} ({full_duration:.1f}s)")
    if focused:
        print(
            f"- **Focus range:** {format_time(effective_start)} → {format_time(effective_end)} "
            f"({effective_duration:.1f}s)"
        )
    if meta.get("width") and meta.get("height"):
        print(f"- **Resolution:** {meta['width']}x{meta['height']} ({meta.get('codec') or 'unknown codec'})")
    mode = "focused" if focused else "full"
    print(f"- **Frames:** {len(frames)} @ {fps:.3f} fps, {mode} mode (budget {target}, max {max_frames})")
    print(f"- **Frame size:** {args.resolution}px wide")
    if transcript_segments:
        in_range = " in range" if focused else ""
        print(
            f"- **Transcript:** {len(transcript_segments)} segments{in_range} "
            f"(via {transcript_source or 'captions'})"
        )
    elif nemotron_analysis:
        print(f"- **Analysis:** multimodal (via {transcript_source})")
    else:
        print("- **Transcript:** none available")

    if not focused and full_duration > 600:
        mins = int(full_duration // 60)
        print()
        print(
            f"> **Warning:** This is a {mins}-minute video. Frame coverage is sparse at this length — "
            "accuracy degrades noticeably on anything over 10 minutes. For better results, "
            "re-run with `--start HH:MM:SS --end HH:MM:SS` to zoom into a specific section."
        )

    print()
    print("## Frames")
    print()
    print(f"Frames live at: `{work / 'frames'}`")
    print()
    print(
        "**Read each frame path below with the Read tool to view the image.** "
        "Frames are in chronological order; `t=MM:SS` is the absolute timestamp in the source video."
    )
    print()
    for frame in frames:
        print(f"- `{frame['path']}` (t={format_time(frame['timestamp_seconds'])})")

    print()
    print("## Transcript")
    print()
    if transcript_text:
        label = transcript_source or "captions"
        if focused:
            print(f"_Source: {label}. Filtered to {format_time(effective_start)} → {format_time(effective_end)}:_")
        else:
            print(f"_Source: {label}._")
        print()
        print("```")
        print(transcript_text)
        print("```")
    elif nemotron_analysis:
        print(f"_Source: {transcript_source}. Multimodal analysis (audio + visual):_")
        print()
        print(nemotron_analysis)
    elif focused and dl.get("subtitle_path"):
        print(f"_No transcript lines fell inside {format_time(effective_start)} → {format_time(effective_end)}._")
    else:
        setup_py = SCRIPT_DIR / "setup.py"
        print(
            "_No transcript available — proceed with frames only. "
            "Captions were missing and the Whisper/multimodal fallbacks were unavailable "
            "(no API key set, or `--no-whisper`/`--no-multimodal` was used). "
            f"Run `python3 {setup_py}` to enable transcription, then re-run._"
        )

    print()
    print("---")
    print(f"_Work dir: `{work}` — delete when done._")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
