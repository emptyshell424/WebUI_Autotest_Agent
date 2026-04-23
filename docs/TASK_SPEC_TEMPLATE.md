# Task Spec Template

> Purpose: use this file as the implementation spec for one upcoming task in `WebUI_Autotest_Agent`.
> Rule: define the problem and acceptance criteria before writing the solution.

---

## 1. Basic Info

- Task name:
- Owner:
- Date:
- Related modules:
  - [ ] `AutoTest_Frontend`
  - [ ] `AutoTest_Backend`
  - [ ] Data / knowledge base
  - [ ] Tests / experiments
  - [ ] Other:
- Related issue / request source:

## 2. Background

### 2.1 Current State

Describe the current behavior with facts.

### 2.2 Problem

State the actual issue:

- What cannot be done now?
- What is unreliable now?
- What is too expensive, fragile, or hard to demo?

### 2.3 Why Now

Explain why this task matters now:

- Blocks the core demo flow
- Reduces demo stability
- Blocks later iteration
- Has become a debugging or testing bottleneck

## 3. Goals And Non-Goals

### 3.1 Goals

List up to three measurable goals.

1.
2.
3.

### 3.2 Non-Goals

State what this task will not do.

- 
- 

## 4. User Scenarios

Write real usage paths, not slogans.

### Scenario 1

- Role:
- Preconditions:
- Steps:
- Expected result:

### Scenario 2

- Role:
- Preconditions:
- Steps:
- Expected result:

## 5. Scope

### 5.1 In Scope

- 
- 

### 5.2 Out Of Scope

- 
- 

## 6. Functional Requirements

### 6.1 Core Behavior

1.
2.
3.

### 6.2 Error And Edge Cases

- Empty input:
- API failure:
- Model output failure:
- Selenium execution failure:
- Retry / self-heal trigger condition:

### 6.3 Observability

- Required logs:
- Frontend states to display:
- History / metrics fields to add or change:

## 7. Design

### 7.1 End-To-End Flow

Describe the chain in 5-10 lines:

`user input -> frontend interaction -> backend API -> service logic -> storage/logging -> frontend presentation`

### 7.2 Frontend Changes

- Pages / routes:
- Components:
- State management:
- Form / interaction changes:
- Error messaging:
- Loading / empty states:

### 7.3 Backend Changes

- API routes:
- Service / agent logic:
- Prompt / RAG / script generation logic:
- Executor or self-heal logic:
- Error handling:

### 7.4 Data And Storage Changes

- SQLite:
- File outputs:
- Knowledge base index:
- History record shape:
- Migration needed:

### 7.5 API Contract

#### Request

```json
{
  "example": "request"
}
```

#### Response

```json
{
  "example": "response"
}
```

#### Failure Semantics

- `400`:
- `500`:

## 8. Alternatives And Tradeoffs

Include at least one rejected option.

### Option A (Chosen)

- Pros:
- Cons:

### Option B (Rejected)

- Pros:
- Cons:
- Rejection reason:

## 9. Risks And Dependencies

### 9.1 Risks

- Technical risk:
- Data risk:
- Demo risk:
- Regression risk:

### 9.2 Dependencies

- API key / model service:
- Browser driver:
- Local target app or third-party site:
- Existing modules:

## 10. Testing And Acceptance

### 10.1 Test Plan

- Unit tests:
- Integration tests:
- Manual verification:
- New experiment scenarios needed:

### 10.2 Acceptance Criteria

Write these as pass/fail outcomes.

- [ ] Can do
- [ ] Handles failures by
- [ ] Frontend displays the correct state
- [ ] Backend logs are enough for diagnosis
- [ ] Existing main flow still works

## 11. Deliverables

- [ ] Code changes
- [ ] API changes
- [ ] Test cases
- [ ] Experiment record / screenshots
- [ ] README or docs update

## 12. Implementation Steps

Break the work into concrete steps.

1.
2.
3.
4.

## 13. Open Questions

List unknowns that can affect implementation.

1.
2.
3.

---

## Notes

- Prefer measurable facts over vague claims.
- Use non-goals to stop scope creep.
- Acceptance criteria must be directly testable.
- If the task spans frontend and backend, define the API and failure semantics.
- If the task affects the graduation-project demo, add a manual demo path.
