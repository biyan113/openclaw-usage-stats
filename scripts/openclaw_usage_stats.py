#!/usr/bin/env python3

import argparse
import glob
import json
import os
from collections import defaultdict
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


LOCAL_TZ = ZoneInfo(os.environ.get("TZ", "Asia/Shanghai"))


@dataclass
class Totals:
    messages: int = 0
    input: int = 0
    output: int = 0
    cache_read: int = 0
    cache_write: int = 0
    total: int = 0

    def add(self, other: "Totals") -> None:
        self.messages += other.messages
        self.input += other.input
        self.output += other.output
        self.cache_read += other.cache_read
        self.cache_write += other.cache_write
        self.total += other.total

    @property
    def billable_like(self) -> int:
        return self.input + self.output


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Summarize OpenClaw usage from local logs.")
    scope = parser.add_mutually_exclusive_group()
    scope.add_argument("--today", action="store_true", help="Summarize local usage for today.")
    scope.add_argument("--date", help="Summarize a specific local date, format YYYY-MM-DD.")
    scope.add_argument("--last-days", type=int, help="Summarize the last N local days including today.")
    parser.add_argument("--top", type=int, default=5, help="Number of top sessions and cron jobs to show.")
    parser.add_argument("--json", action="store_true", help="Emit JSON.")
    return parser.parse_args()


def day_range_local(day_str: str | None, last_days: int | None, today: bool) -> tuple[datetime, datetime, str]:
    now = datetime.now(LOCAL_TZ)
    if day_str:
        start = datetime.strptime(day_str, "%Y-%m-%d").replace(tzinfo=LOCAL_TZ)
        end = start + timedelta(days=1)
        label = day_str
    elif last_days:
        start_day = now.date() - timedelta(days=last_days - 1)
        start = datetime.combine(start_day, datetime.min.time(), tzinfo=LOCAL_TZ)
        end = datetime.combine(now.date() + timedelta(days=1), datetime.min.time(), tzinfo=LOCAL_TZ)
        label = f"last {last_days} days"
    else:
        start = datetime.combine(now.date(), datetime.min.time(), tzinfo=LOCAL_TZ)
        end = start + timedelta(days=1)
        label = start.date().isoformat()
    return start, end, label


def in_range(ts: datetime, start: datetime, end: datetime) -> bool:
    return start <= ts < end


def parse_iso8601(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(LOCAL_TZ)


def session_files() -> list[str]:
    base = os.path.expanduser("~/.openclaw/agents/main/sessions")
    return sorted(glob.glob(os.path.join(base, "*.jsonl")) + glob.glob(os.path.join(base, "*.jsonl.reset.*")))


def cron_files() -> list[str]:
    return sorted(glob.glob(os.path.expanduser("~/.openclaw/cron/runs/*.jsonl")))


def summarize_sessions(start: datetime, end: datetime) -> tuple[Totals, list[dict]]:
    grand = Totals()
    per_file: dict[str, Totals] = defaultdict(Totals)

    for path in session_files():
        name = os.path.basename(path)
        with open(path, "r", encoding="utf-8") as handle:
            for line in handle:
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if row.get("type") != "message":
                    continue
                if row.get("message", {}).get("role") != "assistant":
                    continue
                usage = row.get("message", {}).get("usage")
                if not usage:
                    continue
                ts = row.get("timestamp")
                if not ts or not in_range(parse_iso8601(ts), start, end):
                    continue

                item = Totals(
                    messages=1,
                    input=usage.get("input", 0),
                    output=usage.get("output", 0),
                    cache_read=usage.get("cacheRead", 0),
                    cache_write=usage.get("cacheWrite", 0),
                    total=usage.get("totalTokens", 0),
                )
                grand.add(item)
                per_file[name].add(item)

    top = [
        {"session": key, **asdict(value), "billable_like": value.billable_like}
        for key, value in sorted(per_file.items(), key=lambda kv: kv[1].total, reverse=True)
    ]
    return grand, top


def summarize_cron(start: datetime, end: datetime) -> tuple[Totals, list[dict]]:
    grand = Totals()
    per_job: dict[str, Totals] = defaultdict(Totals)

    for path in cron_files():
        with open(path, "r", encoding="utf-8") as handle:
            for line in handle:
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                usage = row.get("usage")
                ts_ms = row.get("ts")
                if not usage or not ts_ms:
                    continue
                ts = datetime.fromtimestamp(ts_ms / 1000, tz=LOCAL_TZ)
                if not in_range(ts, start, end):
                    continue
                item = Totals(
                    messages=1,
                    input=usage.get("input_tokens", 0),
                    output=usage.get("output_tokens", 0),
                    total=usage.get("total_tokens", 0),
                )
                grand.add(item)
                per_job[row.get("jobId", "unknown")].add(item)

    top = [
        {"jobId": key, **asdict(value), "billable_like": value.billable_like}
        for key, value in sorted(per_job.items(), key=lambda kv: kv[1].total, reverse=True)
    ]
    return grand, top


def render_text(label: str, session_total: Totals, cron_total: Totals, top_sessions: list[dict], top_jobs: list[dict], top_n: int) -> str:
    combined = Totals()
    combined.add(session_total)
    combined.add(cron_total)

    lines = [
        f"Range: {label}",
        f"Total tokens: {combined.total}",
        f"Input tokens: {combined.input}",
        f"Output tokens: {combined.output}",
        f"Cache read tokens: {combined.cache_read}",
        f"Approx billable tokens: {combined.billable_like}",
        "",
        f"Sessions: {session_total.total} total tokens across {session_total.messages} assistant messages",
        f"Cron: {cron_total.total} total tokens across {cron_total.messages} runs",
        "",
        f"Top {top_n} sessions:",
    ]

    if top_sessions:
        for item in top_sessions[:top_n]:
            lines.append(
                f"- {item['session']}: total={item['total']}, input={item['input']}, output={item['output']}, cacheRead={item['cache_read']}"
            )
    else:
        lines.append("- none")

    lines.append("")
    lines.append(f"Top {top_n} cron jobs:")
    if top_jobs:
        for item in top_jobs[:top_n]:
            lines.append(
                f"- {item['jobId']}: total={item['total']}, input={item['input']}, output={item['output']}"
            )
    else:
        lines.append("- none")

    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    start, end, label = day_range_local(args.date, args.last_days, args.today)
    session_total, top_sessions = summarize_sessions(start, end)
    cron_total, top_jobs = summarize_cron(start, end)

    if args.json:
        payload = {
            "range": label,
            "timezone": str(LOCAL_TZ),
            "sessions": asdict(session_total) | {"billable_like": session_total.billable_like},
            "cron": asdict(cron_total) | {"billable_like": cron_total.billable_like},
            "combined": asdict(Totals(
                messages=session_total.messages + cron_total.messages,
                input=session_total.input + cron_total.input,
                output=session_total.output + cron_total.output,
                cache_read=session_total.cache_read + cron_total.cache_read,
                cache_write=session_total.cache_write + cron_total.cache_write,
                total=session_total.total + cron_total.total,
            )),
            "top_sessions": top_sessions[: args.top],
            "top_cron_jobs": top_jobs[: args.top],
        }
        payload["combined"]["billable_like"] = payload["combined"]["input"] + payload["combined"]["output"]
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    print(render_text(label, session_total, cron_total, top_sessions, top_jobs, args.top))


if __name__ == "__main__":
    main()
