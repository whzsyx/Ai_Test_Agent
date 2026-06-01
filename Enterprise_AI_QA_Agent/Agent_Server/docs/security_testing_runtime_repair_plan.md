# Security Testing Runtime Repair Plan

## 1. Goal

This document defines the repair plan for `security_testing` so that campaign execution always reaches a settled state, produces a report on both success and failure paths, and exposes one consistent status model across parent session, child worker session, worker dispatch, and tool jobs.

The repair scope covers:

- `src/modes/security_testing_mode/runtime.py`
- `src/modes/security_testing_mode/subagent_coordinator.py`
- `src/modes/security_testing_mode/campaign_state.py`
- `src/application/orchestration/coordinator_runtime_service.py`
- `src/application/runtime/tool_job_service.py`
- `src/schemas/tool_job.py`
- `src/schemas/session.py`
- `src/modes/security_testing_mode/report_builder.py`
- `src/modes/security_testing_mode/tools.py`

Out of scope for this pass:

- redesigning runner command profiles
- changing the external email provider implementation
- changing non-security modes

## 2. Current Problems

### 2.1 Finalizer is not campaign-settle-driven

`SecurityTestingModeRuntime.handle()` only enters `_finalize_failed_state()` when `state.phase == PHASE_FAILED`. The successful path relies on `_execute_campaign()` to reach `PHASE_REPORT_READY` and then call `_deliver_report_if_requested()`.

This leaves several gaps:

- a campaign can have all tasks and child sessions settled, but the parent phase is still stuck in a running phase
- failure analysis child sessions can settle after the main branch already diverged
- report/email delivery depends on whether the main phase machine reached a specific branch, not whether the campaign actually settled

### 2.2 Status has no single source of truth

Today the same execution is represented independently in at least four places:

- `SecurityTask.status` in `SecurityCampaign.tasks`
- parent `worker_dispatches` records in `session.metadata`
- child `SessionStatus`
- child `ToolJobStatus`

These states are written by different services and can drift. A parent dispatch record can say `running` while the child session is already `failed`, or duplicate the same `task_id` with different states.

### 2.3 `worker_dispatches` is append-based and non-idempotent

`CoordinatorRuntimeService` repeatedly appends launch records into `worker_dispatches`. Follow-up workers and completion workers also append records without canonical upsert semantics. This allows:

- duplicate `task_id` records such as repeated `sec_04`
- inconsistent `child_session_id` backfill
- old `running` records coexisting with newer `failed` or `completed` records

### 2.4 Restricted-access platforms can stall execution

TryHackMe and Hack The Box runs often hit login gates, enrollment pages, lab offline states, or target-only access constraints. Today the system can remain in task execution and failure-analysis loops instead of settling into a reportable constrained-access result.

### 2.5 Report and email delivery are bound to main-session success

The current report/email trigger is phase-based. The desired behavior is campaign-settle-based:

- success path should deliver
- partial-failure path should deliver
- constrained-access path should deliver
- failed-with-report path should deliver

## 3. Target State

### 3.1 Introduce a campaign settlement model

Add a canonical derived settlement object to `campaign_state.py`.

Suggested model:

```python
class CampaignSettlement(BaseModel):
    status: str = "running"  # running / settled_success / settled_partial / settled_failed / settled_blocked
    reason: str = ""
    all_tasks_settled: bool = False
    all_workers_settled: bool = False
    report_ready: bool = False
    delivery_ready: bool = False
    finalized_at: str = ""
```

Store it on `SecurityTestingState` as `settlement`.

### 3.2 Define one authoritative status source per layer

Use the following authority rules:

- `SecurityTask.status` is the canonical task execution state for the campaign
- child `SessionStatus` is the canonical state of the worker conversation only
- child `ToolJobStatus` is the canonical state of the runner tool execution only
- parent `worker_dispatch` becomes a projection derived from task plus child session, not a separately-authored truth source
- parent main `SessionStatus` becomes a projection of campaign settlement:
  - `running` while settlement is not terminal
  - `completed` when settlement is `settled_success` or `settled_partial`
  - `failed` when settlement is `settled_failed`

The main rule is: only one component owns each status, and every other place mirrors it.

## 4. Repair Design

### 4.1 Repair the `security_testing` main runtime finalizer

Add a new method in `runtime.py`:

- `_evaluate_campaign_settlement(state, context) -> SecurityTestingState`

Responsibilities:

- inspect all `SecurityTask.status`
- inspect all referenced `worker_session_id`
- inspect child-session-backed failure-analysis workers
- decide whether the campaign is still running or terminal
- set `state.settlement`
- call final report generation exactly once

Add a second method:

- `_finalize_settled_campaign(state, context) -> SecurityTestingState`

Responsibilities:

- build the final report for all terminal settlement states
- route to delivery based on `state.settlement.delivery_ready`
- update parent session status via a single helper
- guarantee idempotency if called multiple times

Important behavior:

- every checkpoint path should call `_evaluate_campaign_settlement()`
- if settlement is terminal and `state.report is None`, call `_finalize_settled_campaign()`
- if settlement is terminal and report already exists, skip rebuild and only reconcile delivery state

### 4.2 Replace phase-driven delivery with settlement-driven delivery

Change the trigger from:

- "main phase reached `PHASE_REPORT_READY`"

to:

- "campaign settlement is terminal"

Implementation guidance:

- `_deliver_report_if_requested()` should be invoked from `_finalize_settled_campaign()`
- email should be attempted for:
  - `settled_success`
  - `settled_partial`
  - `settled_blocked`
  - `settled_failed`
- delivery failure must not move the campaign back into execution

Suggested phase semantics after this change:

- `PHASE_TASK_RUNNING` means still executing
- `PHASE_RECON_COMPLETE` means tasks settled but report not yet materialized
- `PHASE_REPORT_READY` means final report exists for any terminal outcome
- `PHASE_EMAIL_DELIVERED` means report exists and email delivery succeeded
- `PHASE_FAILED` should represent unrecoverable runtime failure before settlement evaluation, not the normal "campaign ended badly" path

### 4.3 Make `worker_dispatches` idempotent and deduplicated

Introduce a dedicated helper in `CoordinatorRuntimeService`:

- `_upsert_worker_dispatch(parent_session, dispatch_record) -> None`

Rules:

- key by `task_id`
- if record exists, merge instead of append
- preserve the first non-empty `child_session_id`
- allow monotonic status transitions only
- reject backward transitions such as `completed -> running`

Recommended status ordering:

- `pending`
- `dispatching`
- `running`
- `waiting_approval`
- `completed`
- `failed`
- `interrupted`

Store dispatches internally as a map:

- `session.metadata["worker_dispatch_index"] = {task_id: record}`

Optionally keep `worker_dispatches` for API compatibility, but rebuild it from the index before save:

- `worker_dispatches = sorted(index.values(), key=created_at/task_id)`

All current append sites should be refactored to use the upsert helper:

- initial dispatch registration
- follow-up worker registration
- completion worker registration
- worker status updates
- failure-analysis worker registration if surfaced to the parent

### 4.4 Unify task, child session, and tool job state reconciliation

Add a runtime-level reconciliation helper:

- `_reconcile_task_runtime_state(task, child_session, tool_jobs) -> SecurityTask`

Rules:

- if a structured runner output exists, it wins for task result classification
- else if tool job is terminal failed, task becomes failed
- else if child session is terminal failed/interrupted, task becomes failed unless explicitly marked blocked
- else if child session is `waiting_approval`, task remains running and not settled
- else if child session is completed but no runner payload exists, classify as failed or blocked based on assistant summary

Add a blocked classification for constrained platforms:

- `task.failure_analysis["failure_category"] = "restricted_access"`
- `task.status = TASK_FAILED`
- `task.result_summary` should explicitly state coverage limitation

Do not treat `waiting_approval` as settled in security mode unless the parent has decided to terminate the campaign with a blocked report.

This requires changing both:

- `SecuritySubagentCoordinator._wait_for_sessions()`
- `SecurityTestingModeRuntime._wait_for_worker_sessions()`

Current logic incorrectly treats `SessionStatus.waiting_approval` as settled.

### 4.5 Add constrained-access fallback for TryHackMe and HTB

Extend request/platform handling so that TryHackMe and HTB can settle with a report even when active execution cannot proceed.

Add a constrained-access detector in the runtime path, based on:

- platform label
- worker assistant summary
- runner parsed result
- failure-analysis output

Suggested trigger phrases:

- login required
- subscription required
- room locked
- target offline
- VPN required
- machine not deployed
- access denied
- auth wall

When detected:

- mark affected tasks as failed with category `restricted_access`
- add a campaign limitation note
- stop retry/failure-analysis loops for those tasks
- allow the campaign to settle into `settled_blocked` or `settled_partial`
- always generate a report containing:
  - what was attempted
  - what access constraint blocked deeper coverage
  - what passive evidence was still collected
  - next operator action needed

### 4.6 Separate final report ownership from parent session status

Today parent session status and report delivery are too tightly coupled. Introduce explicit ownership:

- `SecurityTestingState.settlement` owns whether execution is done
- `SecurityTestingState.report` owns whether a deliverable exists
- `SecurityTestingState.delivery` owns whether the report was sent
- `SessionStatus` only mirrors campaign settlement and should never gate report creation

This makes "failed-with-report" a first-class outcome instead of an accidental branch.

## 5. File-Level Changes

### 5.1 `src/modes/security_testing_mode/campaign_state.py`

Add:

- `CampaignSettlement`
- `settlement` field on `SecurityTestingState`
- optional `dispatch_version` or `updated_at` fields on task/dispatch-related records if needed for conflict resolution

### 5.2 `src/modes/security_testing_mode/runtime.py`

Add or change:

- `_evaluate_campaign_settlement()`
- `_finalize_settled_campaign()`
- `_reconcile_task_runtime_state()`
- `_mark_campaign_blocked_by_access()`
- `_sync_parent_session_status_from_settlement()`

Refactor:

- `_execute_campaign()`
- `_finalize_failed_state()`
- `_deliver_report_if_requested()`
- `_wait_for_worker_sessions()`
- failure-analysis dispatch handling

### 5.3 `src/modes/security_testing_mode/subagent_coordinator.py`

Change:

- stop treating `waiting_approval` as a settled terminal result
- classify no-runner-output sessions through a shared helper
- upsert child session result back onto the owning task deterministically

### 5.4 `src/application/orchestration/coordinator_runtime_service.py`

Add:

- `_upsert_worker_dispatch()`
- `_normalize_dispatch_status_transition()`
- `_rebuild_worker_dispatches_from_index()`

Refactor:

- `_register_worker_dispatches()`
- `_mark_worker_status()`
- `_maybe_launch_followup_workers()`
- completion worker registration

### 5.5 `src/application/runtime/tool_job_service.py` and `src/schemas/tool_job.py`

Add optional metadata to help reconciliation:

- `security_task_id`
- `worker_session_id`
- `campaign_id`
- `terminal_reason`

This lets runtime correlate child tool jobs back to the owning security task without string matching.

## 6. Acceptance Criteria

The repair is complete only when all of the following are true:

1. A security campaign with all worker tasks settled always reaches either `PHASE_REPORT_READY` or `PHASE_EMAIL_DELIVERED`.
2. A campaign that ends with failed tasks still produces a report and optional email delivery.
3. TryHackMe or HTB access barriers no longer leave the runtime stuck in execution.
4. `worker_dispatches` contains one record per `task_id`.
5. Parent session, task state, child session, and tool job no longer contradict each other at terminal state.
6. Report/email delivery occurs when the campaign is settled, not only when the main session is successful.

## 7. Test Plan

Add or update tests for the following scenarios:

- successful campaign: all tasks complete, report generated, email sent
- partial failure campaign: some tasks fail, report still generated, email still sent
- blocked-access campaign: TryHackMe/HTB task blocked, report generated with limitations
- duplicate dispatch prevention: repeated registration of `sec_04` updates one record only
- terminal reconciliation: child session failed while tool job partial/completed metadata exists
- no-runner-output child session: task settles as failed or blocked, not hanging
- failure-analysis child worker missing: campaign still settles and report is produced
- delivery failure: report exists, settlement stays terminal, delivery marked failed

Recommended file targets:

- `tests/modes/security_testing_mode/test_runtime.py`
- `tests/modes/security_testing_mode/test_subagent_coordinator.py`
- `tests/application/orchestration/test_coordinator_runtime_service.py`
- `tests/application/runtime/test_tool_job_service.py`

## 8. Implementation Order

1. Add `CampaignSettlement` and runtime settlement evaluation.
2. Refactor report finalization and delivery to be settlement-driven.
3. Refactor `worker_dispatches` into an indexed upsert model.
4. Add runtime reconciliation across task, child session, and tool jobs.
5. Add constrained-access classification and blocked-report fallback.
6. Add regression tests for success, partial, blocked, and failed-with-report paths.

## 9. Rollout Notes

- Keep `worker_dispatches` response shape backward compatible during the transition.
- If existing sessions lack `settlement`, derive it lazily on next runtime entry.
- Do not delete old metadata immediately; write the new indexed form and continue emitting the list form until UI/API consumers are updated.
- Prefer adding a single runtime reconciliation pass instead of more one-off status writes.
