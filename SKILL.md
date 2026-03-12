---
name: openclaw-usage-stats
description: Inspect OpenClaw token usage from local session logs and cron run logs. Use this skill whenever the user asks how many tokens OpenClaw used today, on a specific date, in the last N days, by session, by cron job, or wants a local usage audit that does not rely only on UI counters.
---

# OpenClaw Usage Stats

Use local OpenClaw logs as the source of truth for token totals.

## When to use

Use this skill when the user wants:

- today's token usage
- usage for a specific day such as `2026-03-12`
- usage over the last `N` days
- top sessions or top cron jobs by token consumption
- a local cross-check against `openclaw status --usage`

## Data sources

Read from:

- `~/.openclaw/agents/main/sessions/*.jsonl`
- `~/.openclaw/agents/main/sessions/*.jsonl.reset.*`
- `~/.openclaw/cron/runs/*.jsonl`

Interpret fields as:

- session messages: `.message.usage.input`, `.output`, `.cacheRead`, `.cacheWrite`, `.totalTokens`
- cron runs: `.usage.input_tokens`, `.output_tokens`, `.total_tokens`

## Workflow

1. If available, run `openclaw status --usage` for provider quota context.
2. Run `scripts/openclaw_usage_stats.py` for the local audit totals.
3. Report both:
   - billable-like usage: `input + output`
   - raw total usage: includes cached reads when present
4. Call out that `cacheRead` may not map 1:1 to billing.

## Commands

Examples:

```bash
python3 scripts/openclaw_usage_stats.py --today
python3 scripts/openclaw_usage_stats.py --date 2026-03-12
python3 scripts/openclaw_usage_stats.py --last-days 7
python3 scripts/openclaw_usage_stats.py --today --top 10
python3 scripts/openclaw_usage_stats.py --date 2026-03-12 --json
```

## Reporting format

Keep the answer compact and include:

- date range
- total tokens
- input tokens
- output tokens
- cache read tokens if present
- `input + output` as the safest approximate billing number
- top sessions and top cron jobs when relevant

If no logs are found, say that clearly and mention the expected log paths.
