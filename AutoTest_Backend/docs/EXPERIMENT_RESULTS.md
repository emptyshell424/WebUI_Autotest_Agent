# Experiment Results

更新时间：2026-04-22

## 1. Purpose

This file is the formal experiment record for the graduation-project demo.

It does **not** treat "scenario idea exists" as "experiment completed".

Each entry must state:

- the scenario
- whether it was actually executed
- first-pass outcome
- self-heal outcome
- evidence source
- what is still missing

## 2. Batch Summary

### Batch `2026-04-22-baseline`

- Goal: establish a defensible baseline after fixing backend test reproducibility
- Scope: backend automated validation and experiment-document structure
- Result:
  - Automated backend baseline: `30/30` passed
  - Frontend build baseline: pending re-run in a future batch
  - Manual browser scenarios: not executed in this batch
  - Real screenshot evidence: not collected in this batch

### Evidence

- Backend test command: `python AutoTest_Backend/run_backend_tests.py`
- Backend test result: `30/30 OK`
- Related plan update: `docs/UNFINISHED_TASKS.md`

## 3. Result Status Definitions

- `Verified`: executed and has concrete evidence
- `Pending`: planned but not executed in a formal batch
- `Blocked`: cannot be executed yet because prerequisites are missing

## 4. Experiment Inventory

| ID | Scenario Type | Scenario | First Pass | Self-Heal | Final Status | Evidence | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| B-01 | Automated baseline | Backend regression suite via `run_backend_tests.py` | 30/30 pass | Not applicable | Verified | Command output from 2026-04-22 baseline batch | Confirms current backend baseline is reproducible. |
| F-01 | First-pass generation | Open a login page, enter credentials, submit, and verify dashboard welcome text | Pending | Pending | Pending | None yet | Needs local target app and formal run record. |
| F-02 | First-pass generation | Open a search engine, search a keyword, and verify results container appears | Pending | Pending | Pending | None yet | Good candidate for first full manual batch. |
| F-03 | First-pass generation | Open a registration form, fill required fields, submit, and verify success message | Pending | Pending | Pending | None yet | Requires stable form target. |
| F-04 | First-pass generation | Open a list page, search by keyword, and verify filtered row appears | Pending | Pending | Pending | None yet | Useful for table/filter demo. |
| F-05 | First-pass generation | Open a detail page, click a tab, and verify tab content becomes visible | Pending | Pending | Pending | None yet | Useful for navigation/state demo. |
| C-01 | Complex interaction | Verify asynchronously loaded card list | Pending | Pending | Pending | None yet | Should capture wait strategy behavior. |
| C-02 | Complex interaction | Operate inside a dialog and verify confirmation banner | Pending | Pending | Pending | None yet | Useful for modal locator strategy evidence. |
| C-03 | Complex interaction | Switch into iframe, submit form, verify success message | Pending | Pending | Pending | None yet | Should show frame-handling behavior. |
| C-04 | Complex interaction | Open new window and verify destination title | Pending | Pending | Pending | None yet | Needs stable pop-up target. |
| C-05 | Complex interaction | Handle alert/confirm and verify state change | Pending | Pending | Pending | None yet | Useful for dialog support evidence. |
| H-01 | Self-heal | Broken button selector repaired after first failure | Pending | Pending | Pending | None yet | Should record original error and repaired code. |
| H-02 | Self-heal | Input selector changed from `id` to `name` and repaired | Pending | Pending | Pending | None yet | Good targeted self-heal case. |
| H-03 | Self-heal | Wait too short on delayed content and repaired | Pending | Pending | Pending | None yet | Should show timeout-to-wait repair path. |
| H-04 | Self-heal | Target moved inside iframe and repaired | Pending | Pending | Pending | None yet | Should show context-switch repair. |
| H-05 | Self-heal | Dialog interaction repaired to target dialog container | Pending | Pending | Pending | None yet | Should show container scope repair. |

## 5. What Is Already Proven

The following claims currently have evidence:

1. The backend automated baseline is reproducible on the current codebase.
2. The backend test harness no longer fails because of test runtime directory permissions.
3. The RAG retrieval path currently passes targeted regression coverage, including the earlier chunk-selection failure case.

## 6. What Is Not Yet Proven

The following claims should **not** be stated as completed in a defense:

1. A formal manual experiment batch for login/search/form/table/tab scenarios
2. A formal self-heal experiment batch with before/after screenshots
3. Frontend interaction correctness beyond successful build
4. Cross-run trend metrics from repeated experiment batches

## 7. Required Evidence For Next Batch

For each manual scenario in the next batch, record:

- scenario id
- target app / page
- natural-language input
- generated script summary
- first-pass result
- whether self-heal triggered
- repaired script summary
- final result
- screenshot paths
- execution history id or log location

Recommended screenshot set:

- input/request screen
- first failure screen
- self-heal result screen
- history record screen
- metrics screen after batch completion

## 8. Suggested Next Execution Order

1. Run one first-pass batch on a stable local target app and fill `F-01` to `F-05`.
2. Run one self-heal batch with controlled selector/wait regressions and fill `H-01` to `H-05`.
3. Re-run frontend build and, once frontend tests exist, attach them as additional automated baseline evidence.
4. Add screenshots and history ids immediately after each batch instead of backfilling later.

## 9. Appendix: Current Sources

- Scenario source: `AutoTest_Backend/docs/EXPERIMENT_SCENARIOS.md`
- Plan source: `docs/UNFINISHED_TASKS.md`
- Task spec: `docs/TASK_SPEC_EXPERIMENT_RESULTS.md`
- Baseline validation command: `python AutoTest_Backend/run_backend_tests.py`
