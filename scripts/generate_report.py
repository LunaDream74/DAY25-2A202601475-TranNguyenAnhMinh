from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def replace_block(text: str, name: str, replacement: str) -> str:
    """Replace a named generated block while retaining its marker comments."""
    start = f"<!-- {name}:START -->"
    end = f"<!-- {name}:END -->"
    if start not in text or end not in text:
        raise ValueError(f"Missing report markers for {name}")
    before, remainder = text.split(start, maxsplit=1)
    _, after = remainder.split(end, maxsplit=1)
    return f"{before}{start}\n{replacement.rstrip()}\n{end}{after}"


def render_slo_table(metrics: dict[str, Any]) -> str:
    availability = float(metrics["availability"])
    latency_p95 = float(metrics["latency_p95_ms"])
    fallback_rate = float(metrics["fallback_success_rate"])
    cache_rate = float(metrics["cache_hit_rate"])
    recovery = metrics["recovery_time_ms"]
    recovery_value = float(recovery) if recovery is not None else None

    def met(condition: bool) -> str:
        return "Có" if condition else "Không"

    recovery_text = f"{recovery_value:.2f} ms" if recovery_value is not None else "Không ghi nhận"
    recovery_met = recovery_value is not None and recovery_value < 5000
    return "\n".join(
        [
            "| SLI | Mục tiêu | Kết quả | Đạt? |",
            "|---|---:|---:|---|",
            f"| Availability | >= 99% | {availability:.2%} | {met(availability >= 0.99)} |",
            f"| Latency P95 | < 2500 ms | {latency_p95:.2f} ms | {met(latency_p95 < 2500)} |",
            f"| Fallback success rate | >= 95% | {fallback_rate:.2%} | {met(fallback_rate >= 0.95)} |",
            f"| Cache hit rate | >= 10% | {cache_rate:.2%} | {met(cache_rate >= 0.10)} |",
            f"| Recovery time | < 5000 ms | {recovery_text} | {met(recovery_met)} |",
        ]
    )


def render_metrics_table(metrics: dict[str, Any]) -> str:
    recovery = metrics["recovery_time_ms"]
    recovery_text = f"{float(recovery):.2f} ms" if recovery is not None else "Không ghi nhận"
    rows = [
        ("Tổng số yêu cầu", str(metrics["total_requests"])),
        ("Availability", f"{float(metrics['availability']):.4f}"),
        ("Error rate", f"{float(metrics['error_rate']):.4f}"),
        ("Latency P50", f"{float(metrics['latency_p50_ms']):.2f} ms"),
        ("Latency P95", f"{float(metrics['latency_p95_ms']):.2f} ms"),
        ("Latency P99", f"{float(metrics['latency_p99_ms']):.2f} ms"),
        ("Fallback success rate", f"{float(metrics['fallback_success_rate']):.4f}"),
        ("Cache hit rate", f"{float(metrics['cache_hit_rate']):.4f}"),
        ("Circuit open count", str(metrics["circuit_open_count"])),
        ("Recovery time", recovery_text),
        ("Estimated cost", f"{float(metrics['estimated_cost']):.6f} USD"),
        ("Estimated cost saved", f"{float(metrics['estimated_cost_saved']):.6f} USD"),
    ]
    lines = ["| Chỉ số | Giá trị |", "|---|---:|"]
    lines.extend(f"| {name} | {value} |" for name, value in rows)
    return "\n".join(lines)


def render_scenario_status(metrics: dict[str, Any]) -> str:
    scenarios = metrics.get("scenarios", {})
    if not isinstance(scenarios, dict):
        raise TypeError("metrics.scenarios must be an object")
    lines = ["| Trạng thái tổng hợp | Kết quả |", "|---|---|"]
    lines.extend(f"| `{name}` | {status} |" for name, status in scenarios.items())
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--metrics", default="reports/metrics.json")
    parser.add_argument("--out", default="reports/final_report.md")
    args = parser.parse_args()

    metrics = json.loads(Path(args.metrics).read_text(encoding="utf-8"))
    output_path = Path(args.out)
    if not output_path.exists():
        raise FileNotFoundError(
            f"{output_path} is the reviewed report source and must exist before refreshing metrics"
        )

    report = output_path.read_text(encoding="utf-8")
    report = replace_block(report, "SLO_TABLE", render_slo_table(metrics))
    report = replace_block(report, "METRICS_TABLE", render_metrics_table(metrics))
    report = replace_block(report, "SCENARIO_STATUS", render_scenario_status(metrics))
    output_path.write_text(report, encoding="utf-8")
    print(f"refreshed metrics in {output_path}")


if __name__ == "__main__":
    main()
