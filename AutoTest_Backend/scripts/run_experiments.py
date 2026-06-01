"""
Experiment runner for thesis data collection.
Runs 方案A (no-RAG, no-self-heal) and 方案C (Agent ReAct) against the running backend.

Usage:
    1. Start backend: uvicorn app.main:app --reload --port 8000
    2. Run: python scripts/run_experiments.py
    3. Results saved to scripts/experiment_results/

方案A: retrieval_mode="none", MAX_SELF_HEAL_ATTEMPTS=0
方案C: POST /api/v1/agent/run/stream (SSE)
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "app.db"
OUTPUT_DIR = Path(__file__).resolve().parent / "experiment_results"
BASE_URL = "http://localhost:8000/api/v1"


def load_prompts(limit: int | None = None) -> list[dict[str, str]]:
    """Load unique prompts from the database."""
    conn = sqlite3.connect(str(DB_PATH))
    rows = conn.execute(
        "SELECT DISTINCT prompt FROM test_case ORDER BY prompt"
    ).fetchall()
    conn.close()
    prompts = [{"id": str(i + 1).zfill(3), "prompt": r[0]} for i, r in enumerate(rows)]
    if limit:
        prompts = prompts[:limit]
    print(f"Loaded {len(prompts)} unique prompts")
    return prompts


def set_self_heal(value: int) -> bool:
    """Set MAX_SELF_HEAL_ATTEMPTS via settings API. Must send all three fields."""
    try:
        resp = requests.put(
            f"{BASE_URL}/settings",
            json={
                "execution_timeout_seconds": 600,
                "max_self_heal_attempts": value,
                "max_concurrent_executions": 1,
            },
            timeout=10,
        )
        return resp.status_code == 200
    except requests.RequestException as e:
        print(f"  Failed to set self-heal: {e}")
        return False


def generate_case(prompt: str, retrieval_mode: str, timeout: int = 120) -> dict[str, Any]:
    """Call POST /generate and return the result."""
    started = time.monotonic()
    try:
        resp = requests.post(
            f"{BASE_URL}/generate",
            json={"prompt": prompt, "retrieval_mode": retrieval_mode},
            timeout=timeout,
        )
        elapsed_ms = int((time.monotonic() - started) * 1000)
        if resp.status_code == 200:
            data = resp.json()
            return {
                "success": True,
                "case_id": data.get("case", {}).get("id", ""),
                "code": data.get("case", {}).get("generated_code", ""),
                "error": None,
                "elapsed_ms": elapsed_ms,
                "retrieval_mode": data.get("rag_result", {}).get("retrieval_mode", retrieval_mode),
                "rag_sources": data.get("rag_result", {}).get("sources", []),
                "rag_result_count": data.get("rag_result", {}).get("result_count", 0),
            }
        else:
            return {
                "success": False,
                "case_id": None,
                "code": None,
                "error": f"HTTP {resp.status_code}: {resp.text[:200]}",
                "elapsed_ms": elapsed_ms,
                "retrieval_mode": retrieval_mode,
                "rag_sources": [],
                "rag_result_count": 0,
            }
    except requests.RequestException as e:
        elapsed_ms = int((time.monotonic() - started) * 1000)
        return {
            "success": False,
            "case_id": None,
            "code": None,
            "error": str(e),
            "elapsed_ms": elapsed_ms,
            "retrieval_mode": retrieval_mode,
            "rag_sources": [],
            "rag_result_count": 0,
        }


def run_execution(case_id: str, poll_timeout: int = 180, poll_interval: float = 2.0) -> dict[str, Any]:
    """Call POST /executions and poll until complete."""
    started = time.monotonic()
    try:
        resp = requests.post(
            f"{BASE_URL}/executions",
            json={"test_case_id": case_id},
            timeout=10,
        )
        if resp.status_code != 200:
            return {
                "success": False,
                "execution_id": None,
                "status": "api_error",
                "error": f"HTTP {resp.status_code}: {resp.text[:200]}",
                "elapsed_ms": int((time.monotonic() - started) * 1000),
                "self_heal_count": 0,
            }
        exec_data = resp.json()
        exec_id = exec_data.get("id", "")
    except requests.RequestException as e:
        return {
            "success": False,
            "execution_id": None,
            "status": "api_error",
            "error": str(e),
            "elapsed_ms": int((time.monotonic() - started) * 1000),
            "self_heal_count": 0,
        }

    # Poll until terminal status
    deadline = time.monotonic() + poll_timeout
    while time.monotonic() < deadline:
        try:
            resp = requests.get(f"{BASE_URL}/executions/{exec_id}", timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                status = data.get("status", "unknown")
                if status in ("completed", "healed_completed", "failed", "healed_failed", "blocked"):
                    elapsed_ms = int((time.monotonic() - started) * 1000)
                    return {
                        "success": status in ("completed", "healed_completed"),
                        "execution_id": exec_id,
                        "status": status,
                        "error": data.get("error"),
                        "elapsed_ms": elapsed_ms,
                        "self_heal_count": data.get("self_heal_count", 0),
                        "self_heal_triggered": data.get("self_heal_triggered", False),
                    }
            time.sleep(poll_interval)
        except requests.RequestException:
            time.sleep(poll_interval)

    return {
        "success": False,
        "execution_id": exec_id,
        "status": "timeout",
        "error": f"Execution did not finish within {poll_timeout}s",
        "elapsed_ms": int((time.monotonic() - started) * 1000),
        "self_heal_count": 0,
    }


def run_agent(prompt: str, timeout: int = 300) -> dict[str, Any]:
    """Call POST /agent/run/stream and parse SSE events."""
    started = time.monotonic()
    try:
        resp = requests.post(
            f"{BASE_URL}/agent/run/stream",
            json={"prompt": prompt, "max_steps": 15},
            stream=True,
            timeout=timeout,
        )
        events: list[dict[str, Any]] = []
        finish_status = None
        summary = None

        for line in resp.iter_lines(decode_unicode=True):
            if line is None:
                continue
            line = line.strip()
            if not line or not line.startswith("data: "):
                continue
            try:
                data = json.loads(line[6:])
            except json.JSONDecodeError:
                continue

            event_type = data.get("event_type", "")
            step = data.get("step", 0)

            if event_type == "thinking":
                events.append({"type": "thinking", "step": step, "data": data.get("data", {}), "timestamp": data.get("timestamp", 0)})
            elif event_type == "action":
                events.append({"type": "action", "step": step, "data": data.get("data", {}), "timestamp": data.get("timestamp", 0)})
            elif event_type == "observation":
                events.append({"type": "observation", "step": step, "data": data.get("data", {}), "timestamp": data.get("timestamp", 0)})
            elif event_type == "finish":
                finish_status = data.get("data", {}).get("status", "unknown")
                events.append({"type": "finish", "step": step, "data": data.get("data", {}), "timestamp": data.get("timestamp", 0)})
            elif event_type == "error":
                events.append({"type": "error", "step": step, "data": data.get("data", {}), "timestamp": data.get("timestamp", 0)})
            elif event_type == "summary":
                summary = data

        elapsed_ms = int((time.monotonic() - started) * 1000)
        total_steps = max((e.get("step", 0) for e in events), default=0)
        thinking_count = sum(1 for e in events if e.get("type") == "thinking")
        action_count = sum(1 for e in events if e.get("type") == "action")
        error_events = [e for e in events if e.get("type") == "error"]

        return {
            "success": finish_status == "success",
            "status": finish_status or "stream_error",
            "elapsed_ms": elapsed_ms,
            "total_steps": total_steps,
            "thinking_count": thinking_count,
            "action_count": action_count,
            "error_count": len(error_events),
            "errors": [e.get("data", {}).get("error", "") for e in error_events],
            "summary": summary,
            "events": events,
        }
    except requests.RequestException as e:
        elapsed_ms = int((time.monotonic() - started) * 1000)
        return {
            "success": False,
            "status": "request_error",
            "error": str(e),
            "elapsed_ms": elapsed_ms,
            "total_steps": 0,
            "thinking_count": 0,
            "action_count": 0,
            "error_count": 1,
            "errors": [str(e)],
            "summary": None,
            "events": [],
        }


def run_plan_a(prompts: list[dict[str, str]]) -> list[dict[str, Any]]:
    """Run 方案A: no RAG, no self-heal."""
    print("\n" + "=" * 60)
    print("方案A: retrieval_mode='none', self_heal=0")
    print("=" * 60)

    if not set_self_heal(0):
        print("ERROR: Could not disable self-heal. Aborting.")
        return []

    results: list[dict[str, Any]] = []
    for i, p in enumerate(prompts):
        pid = p["id"]
        prompt_text = p["prompt"]
        short = prompt_text[:60] + "..." if len(prompt_text) > 60 else prompt_text
        print(f"\n[{pid}/{len(prompts)}] {short}")

        # Step 1: Generate
        print("  Generating...", end=" ", flush=True)
        gen = generate_case(prompt_text, retrieval_mode="none")
        if not gen["success"]:
            print(f"FAIL (gen): {gen.get('error', 'unknown')[:80]}")
            results.append({
                "prompt_id": pid,
                "prompt": prompt_text,
                "plan": "A",
                "gen_success": False,
                "gen_elapsed_ms": gen["elapsed_ms"],
                "gen_error": gen["error"],
                "exec_success": None,
                "exec_status": None,
                "exec_elapsed_ms": None,
                "exec_error": None,
                "self_heal_count": None,
            })
            continue
        print(f"OK ({gen['elapsed_ms']}ms) case={gen['case_id'][:8] if gen['case_id'] else '?'}")

        # Step 2: Execute
        print("  Executing...", end=" ", flush=True)
        exec_result = run_execution(gen["case_id"])
        status_icon = "OK" if exec_result["success"] else "FAIL"
        print(f"{status_icon} ({exec_result['elapsed_ms']}ms) status={exec_result['status']}")

        results.append({
            "prompt_id": pid,
            "prompt": prompt_text,
            "plan": "A",
            "gen_success": gen["success"],
            "gen_elapsed_ms": gen["elapsed_ms"],
            "gen_error": gen["error"],
            "exec_success": exec_result["success"],
            "exec_status": exec_result["status"],
            "exec_elapsed_ms": exec_result["elapsed_ms"],
            "exec_error": exec_result["error"],
            "self_heal_count": exec_result.get("self_heal_count"),
        })

    return results


def run_plan_c(prompts: list[dict[str, str]]) -> list[dict[str, Any]]:
    """Run 方案C: Agent ReAct mode."""
    print("\n" + "=" * 60)
    print("方案C: Agent ReAct mode")
    print("=" * 60)

    results: list[dict[str, Any]] = []
    for i, p in enumerate(prompts):
        pid = p["id"]
        prompt_text = p["prompt"]
        short = prompt_text[:60] + "..." if len(prompt_text) > 60 else prompt_text
        print(f"\n[{pid}/{len(prompts)}] {short}")

        print("  Agent running...", end=" ", flush=True)
        agent_result = run_agent(prompt_text)
        status_icon = "OK" if agent_result["success"] else "FAIL"
        print(f"{status_icon} ({agent_result['elapsed_ms']}ms) "
              f"steps={agent_result['total_steps']} "
              f"status={agent_result['status']}")

        results.append({
            "prompt_id": pid,
            "prompt": prompt_text,
            "plan": "C",
            "agent_success": agent_result["success"],
            "agent_status": agent_result["status"],
            "agent_elapsed_ms": agent_result["elapsed_ms"],
            "total_steps": agent_result["total_steps"],
            "thinking_count": agent_result["thinking_count"],
            "action_count": agent_result["action_count"],
            "error_count": agent_result["error_count"],
            "errors": agent_result["errors"],
            "summary": agent_result.get("summary"),
        })

    return results


def compute_stats(results: list[dict[str, Any]], plan: str) -> dict[str, Any]:
    """Compute aggregate statistics from results."""
    total = len(results)
    if total == 0:
        return {"plan": plan, "total": 0}

    if plan == "A":
        gen_success = [r for r in results if r.get("gen_success")]
        exec_success = [r for r in results if r.get("exec_success")]
        gen_times = [r["gen_elapsed_ms"] for r in results if r.get("gen_elapsed_ms")]
        exec_times = [r["exec_elapsed_ms"] for r in results if r.get("exec_elapsed_ms")]
        overall_success = [r for r in results if r.get("gen_success") and r.get("exec_success")]
        return {
            "plan": plan,
            "total_prompts": total,
            "gen_success_rate": f"{len(gen_success)}/{total} ({len(gen_success)/total*100:.1f}%)",
            "exec_success_rate": f"{len(exec_success)}/{len(gen_success)} ({len(exec_success)/max(len(gen_success),1)*100:.1f}%)",
            "overall_success_rate": f"{len(overall_success)}/{total} ({len(overall_success)/total*100:.1f}%)",
            "avg_gen_time_ms": int(sum(gen_times) / len(gen_times)) if gen_times else 0,
            "avg_exec_time_ms": int(sum(exec_times) / len(exec_times)) if exec_times else 0,
            "self_heal_count_total": sum(r.get("self_heal_count", 0) or 0 for r in results),
        }

    if plan == "C":
        agent_success = [r for r in results if r.get("agent_success")]
        agent_times = [r["agent_elapsed_ms"] for r in results if r.get("agent_elapsed_ms")]
        all_steps = [r.get("total_steps", 0) for r in results]
        return {
            "plan": plan,
            "total_prompts": total,
            "agent_success_rate": f"{len(agent_success)}/{total} ({len(agent_success)/total*100:.1f}%)",
            "avg_agent_time_ms": int(sum(agent_times) / len(agent_times)) if agent_times else 0,
            "avg_steps": round(sum(all_steps) / len(all_steps), 1) if all_steps else 0,
            "total_errors": sum(r.get("error_count", 0) for r in results),
        }

    return {"plan": plan, "total": total}


def main():
    global BASE_URL

    parser = argparse.ArgumentParser(description="Thesis experiment runner")
    parser.add_argument("--plan", choices=["A", "C", "all"], default="all",
                        help="Which plan to run (default: all)")
    parser.add_argument("--limit", type=int, default=None,
                        help="Limit number of prompts (for quick tests)")
    parser.add_argument("--skip-plan-a", action="store_true",
                        help="Skip 方案A")
    parser.add_argument("--skip-plan-c", action="store_true",
                        help="Skip 方案C")
    parser.add_argument("--base-url", default=BASE_URL,
                        help="Base URL of the running backend")
    args = parser.parse_args()

    BASE_URL = args.base_url

    # Verify server is running
    try:
        resp = requests.get(f"{BASE_URL}/health", timeout=5)
        if resp.status_code != 200:
            print(f"Backend not healthy: {resp.status_code}")
            sys.exit(1)
        print(f"Backend OK: {BASE_URL}")
    except requests.RequestException:
        print(f"Cannot reach backend at {BASE_URL}. Start the server first.")
        sys.exit(1)

    prompts = load_prompts(limit=args.limit)
    if not prompts:
        print("No prompts found.")
        sys.exit(1)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_id = str(uuid.uuid4())[:8]

    all_results: dict[str, Any] = {
        "run_id": run_id,
        "timestamp": timestamp,
        "prompt_count": len(prompts),
    }

    if not args.skip_plan_a:
        plan_a_results = run_plan_a(prompts)
        plan_a_stats = compute_stats(plan_a_results, "A")
        all_results["plan_a"] = {"stats": plan_a_stats, "details": plan_a_results}

        a_file = OUTPUT_DIR / f"plan_a_{timestamp}_{run_id}.json"
        a_file.write_text(json.dumps(all_results["plan_a"], ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n方案A results saved to {a_file}")
        print_stats(plan_a_stats)

    if not args.skip_plan_c:
        plan_c_results = run_plan_c(prompts)
        plan_c_stats = compute_stats(plan_c_results, "C")
        all_results["plan_c"] = {"stats": plan_c_stats, "details": plan_c_results}

        c_file = OUTPUT_DIR / f"plan_c_{timestamp}_{run_id}.json"
        c_file.write_text(json.dumps(all_results["plan_c"], ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n方案C results saved to {c_file}")
        print_stats(plan_c_stats)

    # Summary file
    summary_file = OUTPUT_DIR / f"summary_{timestamp}_{run_id}.json"
    summary_file.write_text(json.dumps(all_results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nSummary saved to {summary_file}")


def print_stats(stats: dict[str, Any]) -> None:
    print(f"\n--- {stats.get('plan', '?')} 方案 statistics ---")
    for k, v in stats.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
