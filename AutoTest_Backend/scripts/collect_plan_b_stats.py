"""
Collect 方案B statistics from the existing database.
方案B = default retrieval (hybrid_rerank) with self-heal enabled.

Usage: python scripts/collect_plan_b_stats.py
Output: scripts/experiment_results/plan_b_stats.json
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "app.db"
OUTPUT_DIR = Path(__file__).resolve().parent / "experiment_results"


def collect_plan_b_stats() -> dict[str, Any]:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row

    # ── Test cases ──
    test_cases = conn.execute("SELECT * FROM test_case").fetchall()
    total_test_cases = len(test_cases)

    # ── Executions ──
    executions = conn.execute("SELECT * FROM execution_record").fetchall()
    total_executions = len(executions)

    # Execution status breakdown
    exec_statuses = conn.execute(
        "SELECT status, COUNT(*) as cnt FROM execution_record GROUP BY status"
    ).fetchall()
    exec_status_map = {r["status"]: r["cnt"] for r in exec_statuses}
    exec_success = exec_status_map.get("completed", 0) + exec_status_map.get("healed_completed", 0)
    exec_failed = exec_status_map.get("failed", 0) + exec_status_map.get("healed_failed", 0) + exec_status_map.get("blocked", 0)
    exec_pending = exec_status_map.get("pending", 0) + exec_status_map.get("running", 0)

    # ── Self-heal ──
    heal_attempts = conn.execute("SELECT * FROM self_heal_attempt").fetchall()
    total_heal_attempts = len(heal_attempts)
    heal_success = sum(1 for r in heal_attempts if r["status"] == "completed")
    heal_failed = sum(1 for r in heal_attempts if r["status"] == "failed")

    # Executions with and without self-heal (via self_heal_attempt table)
    exec_ids_with_heal = conn.execute(
        "SELECT DISTINCT execution_id FROM self_heal_attempt"
    ).fetchall()
    exec_with_heal = len(exec_ids_with_heal)
    exec_without_heal = total_executions - exec_with_heal

    # ── Execution timing ──
    timing_rows = conn.execute(
        "SELECT started_at, finished_at FROM execution_record "
        "WHERE started_at IS NOT NULL AND finished_at IS NOT NULL"
    ).fetchall()
    exec_times_ms: list[float] = []
    for r in timing_rows:
        try:
            start = datetime.fromisoformat(r["started_at"].replace("Z", "+00:00"))
            end = datetime.fromisoformat(r["finished_at"].replace("Z", "+00:00"))
            exec_times_ms.append((end - start).total_seconds() * 1000)
        except (ValueError, TypeError):
            continue

    avg_exec_time_ms = 0
    median_exec_time_ms = 0
    if exec_times_ms:
        # Exclude outliers: > 5 minutes (300,000 ms) for Selenium tests
        reasonable = [t for t in exec_times_ms if t <= 300_000]
        if reasonable:
            avg_exec_time_ms = int(sum(reasonable) / len(reasonable))
            sorted_times = sorted(reasonable)
            mid = len(sorted_times) // 2
            if len(sorted_times) % 2 == 0:
                median_exec_time_ms = int((sorted_times[mid - 1] + sorted_times[mid]) / 2)
            else:
                median_exec_time_ms = int(sorted_times[mid])

    # ── Generation stats ──
    # A test case that has generated_code (non-empty) is a successful generation
    gen_success = conn.execute(
        "SELECT COUNT(*) as cnt FROM test_case WHERE generated_code IS NOT NULL AND generated_code != ''"
    ).fetchone()["cnt"]
    gen_failed = total_test_cases - gen_success

    # Test cases that have executions
    cases_with_exec = conn.execute(
        "SELECT COUNT(DISTINCT test_case_id) as cnt FROM execution_record"
    ).fetchone()["cnt"]

    # ── Per-case pairing ──
    # Join test_case → latest execution for overall success rate
    pair_rows = conn.execute("""
        SELECT tc.id as case_id, tc.prompt, tc.generated_code, tc.created_at as gen_created,
               er.id as exec_id, er.status as exec_status,
               (SELECT COUNT(*) FROM self_heal_attempt sha WHERE sha.execution_id = er.id) as self_heal_count,
               er.started_at, er.finished_at, er.total_llm_calls
        FROM test_case tc
        LEFT JOIN execution_record er ON er.test_case_id = tc.id
        ORDER BY tc.created_at
    """).fetchall()

    # Group by case_id, take the latest execution
    case_exec_map: dict[str, list[dict]] = {}
    for r in pair_rows:
        cid = r["case_id"]
        if cid not in case_exec_map:
            case_exec_map[cid] = []
        case_exec_map[cid].append(dict(r))

    overall_success_count = 0
    for cid, execs in case_exec_map.items():
        # A case is "overall successful" if at least one execution succeeded
        if any(e["exec_status"] in ("completed", "healed_completed") for e in execs if e["exec_id"]):
            overall_success_count += 1

    conn.close()

    stats = {
        "plan": "B",
        "description": "Default hybrid_rerank retrieval + self-heal enabled",
        "test_cases": {
            "total": total_test_cases,
            "generation_success": gen_success,
            "generation_failed": gen_failed,
            "generation_success_rate": f"{gen_success}/{total_test_cases} ({gen_success/max(total_test_cases,1)*100:.1f}%)",
        },
        "executions": {
            "total": total_executions,
            "success": exec_success,
            "failed": exec_failed,
            "pending_or_running": exec_pending,
            "execution_success_rate": f"{exec_success}/{total_executions} ({exec_success/max(total_executions,1)*100:.1f}%)",
            "status_breakdown": exec_status_map,
        },
        "self_heal": {
            "total_attempts": total_heal_attempts,
            "healed": heal_success,
            "failed": heal_failed,
            "heal_success_rate": f"{heal_success}/{max(total_heal_attempts,1)} ({heal_success/max(total_heal_attempts,1)*100:.1f}%)",
            "executions_with_heal": exec_with_heal,
            "executions_without_heal": exec_without_heal,
        },
        "timing": {
            "avg_execution_time_ms": avg_exec_time_ms,
            "median_execution_time_ms": median_exec_time_ms,
            "execution_count_with_timing": len(exec_times_ms),
            "outliers_excluded": (len(exec_times_ms) - len(reasonable)) if exec_times_ms and reasonable else 0,
        },
        "overall": {
            "cases_with_executions": cases_with_exec,
            "overall_success": overall_success_count,
            "overall_success_rate": f"{overall_success_count}/{cases_with_exec} ({overall_success_count/max(cases_with_exec,1)*100:.1f}%)",
        },
    }

    return stats


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    stats = collect_plan_b_stats()
    out_file = OUTPUT_DIR / "plan_b_stats.json"
    out_file.write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"方案B stats saved to {out_file}")
    print()
    for section, data in stats.items():
        if isinstance(data, dict):
            print(f"--- {section} ---")
            for k, v in data.items():
                print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
