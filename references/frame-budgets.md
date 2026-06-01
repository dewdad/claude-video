# Frame budgets

Hard caps: 100 frames, 2 fps. Best accuracy under 10 min. The script enforces these automatically — this reference is for when you need to explain behavior or choose `--max-frames` / `--fps` overrides.

## Full-video budgets

| Duration | Frames | Notes |
|----------|--------|-------|
| ≤ 30 s | ~30 | ~1-2 fps, dense |
| 30 s – 1 min | ~40 | dense |
| 1 – 3 min | ~60 | comfortable |
| 3 – 10 min | ~80 | sparse but workable |
| > 10 min | 100 | sparse scan; warning printed |

## Focused budgets (`--start` / `--end` set)

| Range | fps | Frames |
|-------|-----|--------|
| ≤ 5 s | 2 | up to 10 |
| 5 – 15 s | 2 | up to 30 |
| 15 – 30 s | ~2 | up to 60 |
| 30 – 60 s | ~1.3 | up to 80 |
| 60 – 180 s | ~0.6 | 100 (cap) |

Transcript is auto-filtered to the same range. Frame timestamps remain absolute (real video timeline, not offset-from-start).

## When to focus

- Explicit time ranges in the user's question ("around 2:30", "the intro", "last 30 seconds")
- Video > ~10 min where the question is about a specific part — focused scan beats a sparse full scan
- Re-runs after a full scan lacked detail in some region
