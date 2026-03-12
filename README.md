# openclaw-usage-stats

OpenClaw skill for auditing token usage from local logs.

## Contents

- `SKILL.md`: skill trigger and workflow
- `scripts/openclaw_usage_stats.py`: local usage aggregator
- `agents/openai.yaml`: UI metadata

## Install

Copy or symlink this folder into your OpenClaw skills directory:

```bash
ln -s /path/to/openclaw-usage-stats ~/.openclaw/workspace/skills/openclaw-usage-stats
```

Or copy it directly:

```bash
cp -R /path/to/openclaw-usage-stats ~/.openclaw/workspace/skills/openclaw-usage-stats
```

## Usage

```bash
python3 scripts/openclaw_usage_stats.py --today
python3 scripts/openclaw_usage_stats.py --date 2026-03-12
python3 scripts/openclaw_usage_stats.py --last-days 7 --top 10
python3 scripts/openclaw_usage_stats.py --today --json
```

The script reads:

- `~/.openclaw/agents/main/sessions/*.jsonl`
- `~/.openclaw/agents/main/sessions/*.jsonl.reset.*`
- `~/.openclaw/cron/runs/*.jsonl`

## Notes

- `Approx billable tokens` means `input + output`.
- `cacheRead` is reported separately because provider billing may treat it differently.
