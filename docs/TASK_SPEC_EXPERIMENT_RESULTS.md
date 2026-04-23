# Task Spec: Graduation Demo Experiment Results

> Purpose: define how the project will turn scenario suggestions into a reproducible experiment record for demo, defense, and portfolio use.
> Rule: only record results that have evidence; pending manual runs must stay explicitly pending.

---

## 1. Basic Info

- Task name: P0 experiment result consolidation
- Owner: Codex
- Date: 2026-04-22
- Related modules:
  - [ ] `AutoTest_Frontend`
  - [x] `AutoTest_Backend`
  - [x] Data / knowledge base
  - [x] Tests / experiments
  - [x] Other: `docs`
- Related issue / request source: `docs/UNFINISHED_TASKS.md` P0 item "补齐答辩级实验结果沉淀"

## 2. Background

### 2.1 Current State

The repository already has a scenario list in `AutoTest_Backend/docs/EXPERIMENT_SCENARIOS.md`, backend automated tests, frontend build validation, and README-level instructions for manual demo flow.

What is missing is the formal experiment record that links:

- scenario definition
- execution prerequisites
- actual result
- evidence source
- self-heal behavior
- summary metrics

### 2.2 Problem

The project currently cannot provide a defense-ready answer to basic evaluation questions:

- Which scenarios have actually been run?
- Which ones were first-pass successes vs self-healed successes?
- What evidence exists for each result?
- Which results are automated and which are still manual/pending?

### 2.3 Why Now

- The backend test baseline is already stable again, so the next blocker is proof material, not execution stability.
- Without a formal experiment record, the project can demo features but cannot defend reproducibility.
- Later frontend testing and CI work should plug into a known experiment record structure instead of adding ad hoc notes.

## 3. Goals And Non-Goals

### 3.1 Goals

1. Create one formal experiment record document with scenario inventory, result table, evidence references, and pending items.
2. Separate verified facts from planned manual experiments so the document stays defensible.
3. Define a repeatable structure that can be updated after each experiment batch.

### 3.2 Non-Goals

- This task does not fabricate manual experiment outcomes that were not executed.
- This task does not add screenshot assets or browser recordings by itself.

## 4. User Scenarios

### Scenario 1

- Role: graduation-project presenter
- Preconditions: backend tests pass; README demo flow is available
- Steps: open the experiment record, explain baseline evidence, and point to pending manual scenarios
- Expected result: the audience can distinguish validated capabilities from still-pending manual evidence

### Scenario 2

- Role: future maintainer
- Preconditions: a new experiment batch has been executed
- Steps: append batch metadata, update the result table, and attach screenshot/log evidence paths
- Expected result: the record can evolve without changing document structure

## 5. Scope

### 5.1 In Scope

- Formal experiment result document
- One task spec for the document structure and acceptance criteria
- Update of project plan to reflect the new artifact

### 5.2 Out Of Scope

- Running browser-based manual demo scenarios that require credentials or target environments
- Producing real screenshot assets in this phase

## 6. Functional Requirements

### 6.1 Core Behavior

1. The experiment document must include scenario groups, concrete scenarios, result status, and evidence source.
2. The document must include a batch summary with counts of verified automated checks and pending manual scenarios.
3. The document must mark pending items explicitly instead of leaving gaps.

### 6.2 Error And Edge Cases

- Empty input: not applicable
- API failure: document should note when a scenario depends on external model access
- Model output failure: document should record whether a scenario expects first-pass success or may rely on self-heal
- Selenium execution failure: document should contain a column for first-pass failure and final outcome
- Retry / self-heal trigger condition: document should capture whether self-heal was expected, observed, or not yet tested

### 6.3 Observability

- Required logs: backend test output, future manual run logs, future execution-history references
- Frontend states to display: not changed in this task
- History / metrics fields to add or change: not changed in this task

## 7. Design

### 7.1 End-To-End Flow

`scenario definition -> experiment batch setup -> automated or manual execution -> collect logs/screenshots/history ids -> update experiment record -> use record for demo/defense`

### 7.2 Frontend Changes

- Pages / routes: none
- Components: none
- State management: none
- Form / interaction changes: none
- Error messaging: none
- Loading / empty states: none

### 7.3 Backend Changes

- API routes: none
- Service / agent logic: none in this phase
- Prompt / RAG / script generation logic: none in this phase
- Executor or self-heal logic: none in this phase
- Error handling: none in this phase

### 7.4 Data And Storage Changes

- SQLite: none
- File outputs: add experiment record markdown file
- Knowledge base index: none
- History record shape: none
- Migration needed: no

### 7.5 API Contract

#### Request

```json
{
  "example": "none"
}
```

#### Response

```json
{
  "example": "none"
}
```

#### Failure Semantics

- `400`: not applicable
- `500`: not applicable

## 8. Alternatives And Tradeoffs

### Option A (Chosen)

- Pros: factual, auditable, aligned with current evidence
- Cons: does not make the project look more complete than it is

### Option B (Rejected)

- Pros: faster to write, looks fuller at first glance
- Cons: mixes assumptions and facts, easy to challenge during defense
- Rejection reason: this would create documentation debt and credibility risk

## 9. Risks And Dependencies

### 9.1 Risks

- Technical risk: manual scenarios still need a stable target app and browser environment
- Data risk: screenshots and run ids can drift if not recorded immediately after execution
- Demo risk: pending manual scenarios may expose evidence gaps if not filled before defense
- Regression risk: low, this phase is documentation-only

### 9.2 Dependencies

- API key / model service: needed for real generation and self-heal experiments
- Browser driver: needed for browser-based experiment runs
- Local target app or third-party site: needed for manual scenario execution
- Existing modules: backend tests, README demo flow, experiment scenario list

## 10. Testing And Acceptance

### 10.1 Test Plan

- Unit tests: keep backend unit/integration tests green
- Integration tests: none added in this phase
- Manual verification: inspect that the record only contains evidenced facts and explicit pending items
- New experiment scenarios needed: yes, for first-pass, complex interaction, and self-heal batches

### 10.2 Acceptance Criteria

- [x] A formal experiment record markdown file exists
- [x] The file separates verified facts from pending manual runs
- [x] The file includes evidence references and batch summary fields
- [x] Project plan references this artifact and the next remaining work
- [x] Existing backend main flow still passes current automated validation

## 11. Deliverables

- [x] Code changes
- [ ] API changes
- [ ] Test cases
- [x] Experiment record / screenshots
- [x] README or docs update

Note: screenshot slots are defined, but actual screenshot assets remain pending.

## 12. Implementation Steps

1. Read the current plan, task template, README, and experiment scenario list.
2. Create a formal experiment result document with a reproducible structure.
3. Fill the document with current verified baseline evidence and explicit pending items.
4. Update the project plan and run baseline verification.

## 13. Open Questions

1. Which local target app will be used as the official defense environment for manual runs?
2. Will manual experiment evidence be stored as screenshots only, or screenshots plus exported execution logs?
3. Should future experiment batches be grouped by scenario type or by product/demo milestone?

---

## Notes

- The document must stay truthful under questioning.
- Every "completed" result should have a concrete evidence source.
