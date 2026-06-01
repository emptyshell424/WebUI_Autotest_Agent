"""Run Scheme C (ReAct Agent) experiments and summarize table-ready metrics.

This script calls the existing backend API. It does not modify application code.

Examples:
    python experiments/run_agent_scheme_c.py --smoke
    python experiments/run_agent_scheme_c.py --limit 30
"""

from __future__ import annotations

import argparse
import csv
import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


BACKEND_URL = "http://127.0.0.1:8000/api/v1"
BACKEND_ROOT = Path(__file__).resolve().parents[1]
RESULT_DIR = BACKEND_ROOT / ".tmp" / "agent_scheme_c_results"

SUCCESS_EXECUTION_STATUSES = {"completed", "healed_completed"}
FAILURE_EXECUTION_STATUSES = {"failed", "healed_failed", "blocked", "cancelled"}
TERMINAL_EXECUTION_STATUSES = SUCCESS_EXECUTION_STATUSES | FAILURE_EXECUTION_STATUSES


@dataclass(frozen=True)
class ExperimentCase:
    case_id: str
    scenario: str
    prompt: str


def build_cases() -> list[ExperimentCase]:
    login_prompts = [
        "打开 http://127.0.0.1:9528/login 登录页面，输入用户名 admin 和密码 111111，点击 Login 按钮，并验证页面成功进入 Dashboard 页面。",
        "Open http://127.0.0.1:9528/login, enter username admin and password 111111, click Login, and verify the Dashboard page appears.",
        "访问本地登录页 http://127.0.0.1:9528/login，使用 admin/111111 登录，确认登录后页面不再停留在 login 页面。",
        "Open the Vue Admin login page, sign in with admin and 111111, then assert that dashboard content is visible.",
        "打开 http://127.0.0.1:9528/login，填写用户名 admin、密码 111111，提交后验证页面中出现 Dashboard。",
        "Use Selenium to log in at http://127.0.0.1:9528/login with admin and 111111, then print Test Completed after success.",
        "测试本地后台系统登录流程：进入登录页，填写 admin 和 111111，点击登录按钮，验证跳转成功。",
        "Open the login route on localhost port 9528, complete the admin login flow, and verify a post-login page anchor.",
        "在 http://127.0.0.1:9528/login 执行登录测试，要求等待输入框可见后再输入账号密码并提交。",
        "Check that user admin can log into the Vue Admin Template at http://127.0.0.1:9528/login with password 111111.",
        "打开登录页面，输入 admin/111111，点击 Login 后验证当前页面已经进入系统首页。",
        "Run a Selenium login test for http://127.0.0.1:9528/login and verify the dashboard route or dashboard text.",
        "访问 http://127.0.0.1:9528/login，完成账号密码登录，并验证页面出现登录后的主体内容。",
        "Create and execute a UI test that logs into the local admin page using admin and 111111.",
        "对 Vue Admin Template 登录功能进行自动化测试：打开登录页、输入账号密码、点击登录并断言成功。",
    ]
    baidu_prompts = [
        "打开百度，搜索 DeepSeek，等待结果页面出现，然后打印测试完成。",
        "Open Baidu, search for DeepSeek, wait for the results page to appear, then print Test Completed.",
        "访问 https://www.baidu.com，输入 Web UI 自动化测试，提交搜索并验证结果页加载。",
        "使用 Selenium 打开百度首页，搜索 Selenium，等待搜索结果区域出现。",
        "Open Baidu and search for RAG, then assert that search results are displayed.",
        "打开百度搜索 OpenAI，等待结果页面加载完成后输出 Test Completed。",
        "Go to Baidu, type 大语言模型 into the search box, submit, and verify a result container exists.",
        "测试百度搜索流程：打开首页、定位搜索框、输入 DeepSeek、回车并验证结果页。",
        "Open https://www.baidu.com, search for Vue 3, and confirm the search results page is visible.",
        "用 Selenium 自动化百度搜索 FastAPI，并在结果页面出现后打印测试完成。",
        "打开百度页面，输入 ChromaDB 作为关键词，提交搜索并等待结果列表。",
        "Open Baidu, search for Playwright, wait until the result page title or result container changes.",
        "访问百度首页，搜索 Python Selenium，确认页面跳转到搜索结果。",
        "Create a UI test that searches Baidu for 自动化测试 and verifies results are shown.",
        "打开百度，搜索 ReAct Agent，等待结果页稳定后输出 Test Completed。",
    ]

    cases: list[ExperimentCase] = []
    for index, (login_prompt, baidu_prompt) in enumerate(
        zip(login_prompts, baidu_prompts, strict=True),
        start=1,
    ):
        cases.append(ExperimentCase(f"login-{index:02d}", "登录认证", login_prompt))
        cases.append(ExperimentCase(f"baidu-{index:02d}", "百度搜索", baidu_prompt))
    return cases


def post_json(url: str, payload: dict[str, Any], timeout: int) -> dict[str, Any]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def get_json(url: str, timeout: int) -> dict[str, Any]:
    with urlopen(url, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def wait_for_execution(
    *,
    base_url: str,
    execution_id: str,
    timeout_seconds: int = 90,
    poll_interval_seconds: float = 3.0,
) -> dict[str, Any]:
    deadline = time.perf_counter() + timeout_seconds
    last_response: dict[str, Any] | None = None
    while time.perf_counter() < deadline:
        last_response = get_json(f"{base_url}/executions/{execution_id}", timeout=60)
        if last_response.get("status") in TERMINAL_EXECUTION_STATUSES:
            return last_response
        time.sleep(poll_interval_seconds)
    return last_response or get_json(f"{base_url}/executions/{execution_id}", timeout=60)


def check_backend(base_url: str, timeout: int) -> None:
    try:
        get_json(f"{base_url}/health", timeout)
    except (HTTPError, URLError, TimeoutError) as exc:
        raise SystemExit(
            f"Backend is not reachable at {base_url}. Start the FastAPI server first. Error: {exc}"
        ) from exc


def tool_counts(events: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for event in events:
        data = event.get("data") or {}
        tool = data.get("tool")
        if event.get("event_type") == "thinking":
            tool = data.get("action")
        if tool:
            counts[tool] = counts.get(tool, 0) + 1
    return counts


def extract_run_metrics(
    *,
    case: ExperimentCase,
    run_response: dict[str, Any],
    execution_response: dict[str, Any] | None,
    duration_seconds: float,
) -> dict[str, Any]:
    events = run_response.get("events") or []
    counts = tool_counts(events)
    execution_status = (execution_response or {}).get("status")
    self_heal_count = int((execution_response or {}).get("self_heal_count") or 0)
    self_heal_triggered = bool((execution_response or {}).get("self_heal_triggered")) or (
        counts.get("diagnose_failure", 0) > 0 or counts.get("repair_script", 0) > 0
    )
    final_success = (
        run_response.get("agent_status") == "success"
        or execution_status in SUCCESS_EXECUTION_STATUSES
    )
    first_pass_success = execution_status == "completed" and not self_heal_triggered

    return {
        "case_id": case.case_id,
        "scenario": case.scenario,
        "prompt": case.prompt,
        "run_id": run_response.get("run_id"),
        "agent_status": run_response.get("agent_status"),
        "steps": run_response.get("steps"),
        "test_case_id": run_response.get("test_case_id"),
        "execution_id": run_response.get("execution_id"),
        "execution_status": execution_status,
        "first_pass_success": first_pass_success,
        "self_heal_triggered": self_heal_triggered,
        "self_heal_count": self_heal_count,
        "final_success": final_success,
        "duration_seconds": round(duration_seconds, 3),
        "search_knowledge_calls": counts.get("search_knowledge", 0),
        "generate_calls": counts.get("generate_selenium_script", 0),
        "validate_calls": counts.get("validate_code", 0),
        "execute_calls": counts.get("execute_script", 0),
        "diagnose_calls": counts.get("diagnose_failure", 0),
        "repair_calls": counts.get("repair_script", 0),
        "finish_calls": counts.get("finish", 0),
        "error": run_response.get("error"),
    }


def rate(numerator: int, denominator: int) -> float:
    return round(numerator / denominator * 100, 1) if denominator else 0.0


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    effective = len(rows)
    first_success = sum(1 for row in rows if row["first_pass_success"])
    heal_triggered = sum(1 for row in rows if row["self_heal_triggered"])
    heal_success = sum(
        1 for row in rows
        if row["self_heal_triggered"] and row["final_success"] and not row["first_pass_success"]
    )
    final_success = sum(1 for row in rows if row["final_success"])
    return {
        "effective_runs": effective,
        "first_pass_success_count": first_success,
        "first_pass_success_rate": rate(first_success, effective),
        "self_heal_triggered_count": heal_triggered,
        "self_heal_triggered_rate": rate(heal_triggered, effective),
        "self_heal_success_count": heal_success,
        "self_heal_success_rate": rate(heal_success, heal_triggered),
        "final_success_count": final_success,
        "final_success_rate": rate(final_success, effective),
        "average_steps": round(sum(int(row["steps"] or 0) for row in rows) / effective, 2) if effective else 0,
        "average_duration_seconds": round(sum(float(row["duration_seconds"]) for row in rows) / effective, 2) if effective else 0,
    }


def write_outputs(rows: list[dict[str, Any]], summary: dict[str, Any], output_dir: Path) -> None:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")

    json_path = output_dir / f"agent_scheme_c_runs_{timestamp}.json"
    csv_path = output_dir / f"agent_scheme_c_summary_{timestamp}.csv"
    md_path = output_dir / f"agent_scheme_c_table_{timestamp}.md"

    table_markdown = "\n".join([
        "| 方案 | 技术路线 | 是否使用 RAG | 是否支持自愈 | 是否支持 Agent 自主规划 | 有效执行次数 | 首次成功率 | 最终成功率 | 平均耗时 |",
        "|---|---|---|---|---|---:|---:|---:|---:|",
        (
            "| 方案 C | ReAct Agent 自主规划 + 工具调用 + 自愈修复 | 是 | 是 | 是 | "
            f"{summary['effective_runs']} | {summary['first_pass_success_rate']}% | "
            f"{summary['final_success_rate']}% | {summary['average_duration_seconds']} s |"
        ),
        "",
        "补充指标：",
        f"- 自愈触发次数：{summary['self_heal_triggered_count']}",
        f"- 自愈触发率：{summary['self_heal_triggered_rate']}%",
        f"- 自愈成功次数：{summary['self_heal_success_count']}",
        f"- 自愈成功率：{summary['self_heal_success_rate']}%",
        f"- 平均 Agent 步数：{summary['average_steps']}",
    ])

    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        json_path.write_text(
            json.dumps({"summary": summary, "runs": rows}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        with csv_path.open("w", encoding="utf-8-sig", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=list(rows[0].keys()) if rows else [])
            if rows:
                writer.writeheader()
                writer.writerows(rows)

        md_path.write_text(table_markdown, encoding="utf-8")

        print(f"Wrote JSON: {json_path}")
        print(f"Wrote CSV:  {csv_path}")
        print(f"Wrote MD:   {md_path}")
    except PermissionError as exc:
        print(f"Could not write result files: {exc}")
        print("TABLE_MARKDOWN_BEGIN")
        print(table_markdown)
        print("TABLE_MARKDOWN_END")
        print("RUNS_JSON_BEGIN")
        print(json.dumps({"summary": summary, "runs": rows}, ensure_ascii=False, indent=2))
        print("RUNS_JSON_END")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default=BACKEND_URL)
    parser.add_argument("--max-steps", type=int, default=15)
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--limit", type=int, default=30)
    parser.add_argument("--smoke", action="store_true", help="Run only 2 cases.")
    parser.add_argument("--output-dir", type=Path, default=RESULT_DIR)
    args = parser.parse_args()

    check_backend(args.base_url, timeout=10)
    cases = build_cases()
    if args.smoke:
        cases = [cases[0], cases[15]]
    else:
        cases = cases[: args.limit]

    rows: list[dict[str, Any]] = []
    for index, case in enumerate(cases, start=1):
        print(f"[{index}/{len(cases)}] Running {case.case_id} ({case.scenario})")
        started = time.perf_counter()
        response = post_json(
            f"{args.base_url}/agent/run",
            {"prompt": case.prompt, "max_steps": args.max_steps},
            timeout=args.timeout,
        )
        duration = time.perf_counter() - started

        execution_id = response.get("execution_id")
        execution_response = None
        if execution_id:
            execution_response = wait_for_execution(
                base_url=args.base_url,
                execution_id=execution_id,
            )

        row = extract_run_metrics(
            case=case,
            run_response=response,
            execution_response=execution_response,
            duration_seconds=duration,
        )
        rows.append(row)
        print(
            "    "
            f"agent={row['agent_status']} execution={row['execution_status']} "
            f"steps={row['steps']} duration={row['duration_seconds']}s"
        )

    summary = summarize(rows)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    write_outputs(rows, summary, args.output_dir)


if __name__ == "__main__":
    main()
