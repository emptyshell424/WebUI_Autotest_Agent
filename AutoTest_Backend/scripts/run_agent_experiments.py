"""Run supplementary Agent-scheme experiments through the local HTTP API.

The script creates real Agent runs by calling:

    POST /api/v1/agent/run

For each run it records the prompt, Agent result, execution result, elapsed
time, first-pass success, self-heal state, and final success. Results are
written as JSONL and CSV files under AutoTest_Backend/experiments.

Usage:
    python scripts/run_agent_experiments.py --limit 3
    python scripts/run_agent_experiments.py --limit 30 --max-steps 15
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any


DEFAULT_BASE_URL = "http://127.0.0.1:8000/api/v1"
TERMINAL_STATUSES = {
    "completed",
    "failed",
    "healed_completed",
    "healed_failed",
    "blocked",
    "cancelled",
}
FINAL_SUCCESS_STATUSES = {"completed", "healed_completed"}


PROMPTS: list[dict[str, str]] = [
    {
        "case_id": "C-LOGIN-01",
        "scene": "login",
        "prompt": (
            "Open http://localhost:9528/login, enter username admin and password "
            "111111, click the Login button, and verify the dashboard page shows "
            "name: Super Admin."
        ),
    },
    {
        "case_id": "C-LOGIN-02",
        "scene": "login",
        "prompt": (
            "Visit http://localhost:9528/login, log in with admin / 111111, wait "
            "until the route contains /dashboard, and assert that Dashboard is visible."
        ),
    },
    {
        "case_id": "C-LOGIN-03",
        "scene": "login",
        "prompt": (
            "Use Selenium to complete the vue-admin-template login flow at "
            "http://localhost:9528/login with username admin and password 111111, "
            "then verify the logged-in user text is Super Admin."
        ),
    },
    {
        "case_id": "C-LOGIN-04",
        "scene": "login",
        "prompt": (
            "Open the local login page http://localhost:9528/login, fill the username "
            "and password inputs, submit the form, and verify that the browser leaves "
            "the login page."
        ),
    },
    {
        "case_id": "C-LOGIN-05",
        "scene": "login",
        "prompt": (
            "Navigate to http://localhost:9528/login, perform a successful admin login, "
            "and confirm that the dashboard container is rendered."
        ),
    },
    {
        "case_id": "C-LOGIN-06",
        "scene": "login",
        "prompt": (
            "Test the login workflow of vue-admin-template: open the login URL, input "
            "admin and 111111, click Login, and assert that the Dashboard page is reached."
        ),
    },
    {
        "case_id": "C-LOGIN-07",
        "scene": "login",
        "prompt": (
            "Start from http://localhost:9528/login and verify that a valid admin login "
            "redirects to the dashboard and shows the Super Admin identity."
        ),
    },
    {
        "case_id": "C-LOGIN-08",
        "scene": "login",
        "prompt": (
            "Open http://localhost:9528/login, wait for the Login Form, submit admin "
            "credentials, and check that the dashboard text appears after login."
        ),
    },
    {
        "case_id": "C-TABLE-01",
        "scene": "table",
        "prompt": (
            "Log in to http://localhost:9528/login with admin / 111111, open "
            "http://localhost:9528/example/table, wait for the Element UI table, and "
            "verify that the headers Title, Author, Pageviews, and Status are visible."
        ),
    },
    {
        "case_id": "C-TABLE-02",
        "scene": "table",
        "prompt": (
            "After logging in to the local vue-admin-template app, navigate to "
            "/example/table and verify that at least one table row is rendered."
        ),
    },
    {
        "case_id": "C-TABLE-03",
        "scene": "table",
        "prompt": (
            "Open the local app, log in as admin, go to the Example Table page, and "
            "assert that the Element UI table container is displayed."
        ),
    },
    {
        "case_id": "C-TABLE-04",
        "scene": "table",
        "prompt": (
            "Use Selenium to log in and verify the table page at "
            "http://localhost:9528/example/table contains the Status column."
        ),
    },
    {
        "case_id": "C-FORM-01",
        "scene": "form",
        "prompt": (
            "Log in to http://localhost:9528/login with admin / 111111, open "
            "http://localhost:9528/form/index, fill Activity name with Test Activity, "
            "and verify that the form page remains visible."
        ),
    },
    {
        "case_id": "C-FORM-02",
        "scene": "form",
        "prompt": (
            "After admin login, navigate to /form/index, wait for the Activity name "
            "input, type UI automation test, and verify the value is entered."
        ),
    },
    {
        "case_id": "C-FORM-03",
        "scene": "form",
        "prompt": (
            "Open the local vue-admin-template form page after login and verify that "
            "labels Activity name, Activity zone, and Resources are displayed."
        ),
    },
    {
        "case_id": "C-FORM-04",
        "scene": "form",
        "prompt": (
            "Log in, open http://localhost:9528/form/index, toggle Instant delivery, "
            "and verify the Element UI form is still displayed."
        ),
    },
    {
        "case_id": "C-NAV-01",
        "scene": "navigation",
        "prompt": (
            "Log in to the local app, open http://localhost:9528/dashboard, then "
            "navigate to http://localhost:9528/example/table and verify the table page."
        ),
    },
    {
        "case_id": "C-NAV-02",
        "scene": "navigation",
        "prompt": (
            "After logging in, navigate between Dashboard and Example Table in the "
            "local vue-admin-template app, and verify each page has a stable visible anchor."
        ),
    },
    {
        "case_id": "C-NAV-03",
        "scene": "navigation",
        "prompt": (
            "Open http://localhost:9528/login, log in, then visit /nested/menu1/menu1-1 "
            "and verify the page loads without returning to the login page."
        ),
    },
    {
        "case_id": "C-BAIDU-01",
        "scene": "baidu_search",
        "prompt": (
            "Open https://www.baidu.com, search for DeepSeek, wait for the results "
            "page, and verify that at least one result link is visible."
        ),
    },
    {
        "case_id": "C-BAIDU-02",
        "scene": "baidu_search",
        "prompt": (
            "Use Selenium to open Baidu, input Web UI automation testing in the search "
            "box, submit the query, and verify the result container appears."
        ),
    },
    {
        "case_id": "C-BAIDU-03",
        "scene": "baidu_search",
        "prompt": (
            "Open the Baidu homepage, search for Selenium Python, and confirm that the "
            "results page contains visible search results."
        ),
    },
    {
        "case_id": "C-BAIDU-04",
        "scene": "baidu_search",
        "prompt": (
            "Navigate to https://www.baidu.com, search for RAG large language model, "
            "and verify that the page shows a results list."
        ),
    },
    {
        "case_id": "C-BAIDU-05",
        "scene": "baidu_search",
        "prompt": (
            "Open Baidu, type vue admin template into the search input, click the search "
            "button, and verify the result area is rendered."
        ),
    },
    {
        "case_id": "C-BAIDU-06",
        "scene": "baidu_search",
        "prompt": (
            "Search Baidu for ChromeDriver Selenium, wait until the results page is "
            "loaded, and print Test Completed when results are visible."
        ),
    },
    {
        "case_id": "C-BAIDU-07",
        "scene": "baidu_search",
        "prompt": (
            "Use Baidu search to query FastAPI Vue, then assert that at least one "
            "search result title is displayed."
        ),
    },
    {
        "case_id": "C-BAIDU-08",
        "scene": "baidu_search",
        "prompt": (
            "Open https://www.baidu.com, search for Element UI table, and verify the "
            "Baidu results container appears."
        ),
    },
    {
        "case_id": "C-BAIDU-09",
        "scene": "baidu_search",
        "prompt": (
            "Open Baidu, search for automated test self healing, wait for the results, "
            "and verify that visible links exist."
        ),
    },
    {
        "case_id": "C-BAIDU-10",
        "scene": "baidu_search",
        "prompt": (
            "Search Baidu for large language model testing agent and verify that the "
            "results page has loaded successfully."
        ),
    },
    {
        "case_id": "C-LOCAL-01",
        "scene": "local_smoke",
        "prompt": (
            "Open http://localhost:9528/login and verify that the Login Form and Login "
            "button are visible without submitting credentials."
        ),
    },
    {
        "case_id": "C-LOCAL-02",
        "scene": "local_smoke",
        "prompt": (
            "Navigate to http://localhost:9528/login and verify that username and "
            "password input fields can be located."
        ),
    },
]


def http_json(method: str, url: str, payload: dict[str, Any] | None = None, timeout: int = 60) -> dict[str, Any]:
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8")
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} {url}: {body}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Cannot connect to {url}: {exc}") from exc


def terminal_execution(base_url: str, execution_id: str | None, timeout_seconds: int) -> dict[str, Any] | None:
    if not execution_id:
        return None
    deadline = time.time() + timeout_seconds
    last: dict[str, Any] | None = None
    while time.time() < deadline:
        last = http_json("GET", f"{base_url}/executions/{execution_id}", timeout=30)
        if last.get("status") in TERMINAL_STATUSES:
            return last
        time.sleep(3)
    return last


def compact_error(execution: dict[str, Any] | None, agent_error: str | None) -> str:
    if agent_error:
        return agent_error[:500]
    if not execution:
        return ""
    text = execution.get("error") or execution.get("logs") or ""
    return str(text).replace("\r", " ").replace("\n", " ")[:500]


def run_one(
    *,
    base_url: str,
    prompt_case: dict[str, str],
    max_steps: int,
    request_timeout: int,
    execution_timeout: int,
) -> dict[str, Any]:
    started = time.time()
    response: dict[str, Any] | None = None
    execution: dict[str, Any] | None = None
    error: str | None = None

    try:
        response = http_json(
            "POST",
            f"{base_url}/agent/run",
            payload={"prompt": prompt_case["prompt"], "max_steps": max_steps},
            timeout=request_timeout,
        )
        execution = terminal_execution(base_url, response.get("execution_id"), execution_timeout)
    except Exception as exc:  # noqa: BLE001 - experiment runner should record failures.
        error = str(exc)

    elapsed = time.time() - started
    execution_status = execution.get("status") if execution else None
    first_pass_success = execution_status == "completed"
    final_success = execution_status in FINAL_SUCCESS_STATUSES
    self_heal_count = int(execution.get("self_heal_count") or 0) if execution else 0
    healed = bool(execution.get("healed")) if execution else False

    events = response.get("events", []) if response else []
    tool_calls = [
        e.get("data", {}).get("tool")
        for e in events
        if e.get("event_type") == "action"
    ]

    return {
        "case_id": prompt_case["case_id"],
        "scene": prompt_case["scene"],
        "prompt": prompt_case["prompt"],
        "agent_status": response.get("agent_status") if response else "error",
        "agent_steps": response.get("steps") if response else 0,
        "test_case_id": response.get("test_case_id") if response else None,
        "execution_id": response.get("execution_id") if response else None,
        "execution_status": execution_status or "missing",
        "first_pass_success": first_pass_success,
        "self_heal_triggered": self_heal_count > 0,
        "self_heal_count": self_heal_count,
        "healed": healed,
        "final_success": final_success,
        "elapsed_seconds": round(elapsed, 2),
        "tool_calls": " -> ".join(t for t in tool_calls if t),
        "error_summary": error or compact_error(execution, response.get("error") if response else None),
    }


def write_outputs(output_dir: Path, rows: list[dict[str, Any]]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = output_dir / "agent_experiment_results.jsonl"
    csv_path = output_dir / "agent_experiment_results.csv"
    summary_path = output_dir / "agent_experiment_summary.json"

    with jsonl_path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    fieldnames = [
        "case_id",
        "scene",
        "agent_status",
        "agent_steps",
        "test_case_id",
        "execution_id",
        "execution_status",
        "first_pass_success",
        "self_heal_triggered",
        "self_heal_count",
        "healed",
        "final_success",
        "elapsed_seconds",
        "error_summary",
        "prompt",
        "tool_calls",
    ]
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    summary = summarize(rows)
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")


def pct(numerator: int, denominator: int) -> float:
    return round(numerator * 100 / denominator, 1) if denominator else 0.0


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(rows)
    first_success = sum(1 for r in rows if r["first_pass_success"])
    heal_triggered = sum(1 for r in rows if r["self_heal_triggered"])
    heal_success = sum(1 for r in rows if r["healed"])
    final_success = sum(1 for r in rows if r["final_success"])
    avg_time = round(sum(float(r["elapsed_seconds"]) for r in rows) / total, 2) if total else 0.0

    by_scene: dict[str, dict[str, Any]] = {}
    for row in rows:
        scene = row["scene"]
        item = by_scene.setdefault(
            scene,
            {
                "count": 0,
                "first_success": 0,
                "heal_triggered": 0,
                "heal_success": 0,
                "final_success": 0,
                "avg_elapsed_seconds": 0.0,
                "_elapsed_total": 0.0,
            },
        )
        item["count"] += 1
        item["first_success"] += int(row["first_pass_success"])
        item["heal_triggered"] += int(row["self_heal_triggered"])
        item["heal_success"] += int(row["healed"])
        item["final_success"] += int(row["final_success"])
        item["_elapsed_total"] += float(row["elapsed_seconds"])

    for item in by_scene.values():
        count = item["count"]
        item["first_success_rate"] = pct(item["first_success"], count)
        item["self_heal_triggered_rate"] = pct(item["heal_triggered"], count)
        item["self_heal_success_rate"] = pct(item["heal_success"], item["heal_triggered"])
        item["final_success_rate"] = pct(item["final_success"], count)
        item["avg_elapsed_seconds"] = round(item["_elapsed_total"] / count, 2) if count else 0.0
        del item["_elapsed_total"]

    return {
        "effective_execution_count": total,
        "first_pass_success_count": first_success,
        "self_heal_triggered_count": heal_triggered,
        "self_heal_success_count": heal_success,
        "final_success_count": final_success,
        "first_pass_success_rate": pct(first_success, total),
        "self_heal_triggered_rate": pct(heal_triggered, total),
        "self_heal_success_rate": pct(heal_success, heal_triggered),
        "final_success_rate": pct(final_success, total),
        "average_elapsed_seconds": avg_time,
        "by_scene": by_scene,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run supplementary Agent experiments.")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="Backend API base URL.")
    parser.add_argument("--limit", type=int, default=len(PROMPTS), help="Number of prompts to run.")
    parser.add_argument("--offset", type=int, default=0, help="Prompt offset for resumed batches.")
    parser.add_argument("--max-steps", type=int, default=15, help="Agent max_steps value.")
    parser.add_argument("--request-timeout", type=int, default=900, help="Timeout for each Agent request.")
    parser.add_argument("--execution-timeout", type=int, default=300, help="Extra polling timeout for execution status.")
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Output directory. Defaults to experiments/agent_YYYYmmdd_HHMMSS.",
    )
    return parser.parse_args()


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    args = parse_args()
    base_url = args.base_url.rstrip("/")

    try:
        health = http_json("GET", f"{base_url}/health", timeout=30)
        print(f"Backend health: {health.get('status')}")
    except Exception as exc:  # noqa: BLE001
        print(f"Backend health check failed: {exc}", file=sys.stderr)
        return 2

    selected = PROMPTS[args.offset : args.offset + args.limit]
    if not selected:
        print("No prompts selected. Check --offset and --limit.", file=sys.stderr)
        return 2

    if args.output_dir:
        output_dir = Path(args.output_dir)
    else:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = Path("experiments") / f"agent_{stamp}"

    rows: list[dict[str, Any]] = []
    for index, prompt_case in enumerate(selected, start=1):
        print(f"[{index}/{len(selected)}] {prompt_case['case_id']} {prompt_case['scene']}")
        row = run_one(
            base_url=base_url,
            prompt_case=prompt_case,
            max_steps=args.max_steps,
            request_timeout=args.request_timeout,
            execution_timeout=args.execution_timeout,
        )
        rows.append(row)
        status = row["execution_status"]
        print(
            "  "
            f"agent={row['agent_status']} exec={status} "
            f"first={row['first_pass_success']} final={row['final_success']} "
            f"heal_count={row['self_heal_count']} elapsed={row['elapsed_seconds']}s"
        )
        write_outputs(output_dir, rows)

    summary = summarize(rows)
    print("\nSummary")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"\nWrote: {output_dir.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
