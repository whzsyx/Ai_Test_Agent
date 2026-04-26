from __future__ import annotations

from collections.abc import Iterable
from uuid import uuid4

from src.domain.models import SessionRecord
from src.registry.modes import ModeRegistry
from src.application.testing.direction_service import QATaskDirectionService
from src.application.testing.router_service import QATaskRouterService
from src.schemas.session import (
    ExecutionRequest,
    InputAttachment,
    InputEnvelope,
    InputHookResult,
    InputRoutingDecision,
    MessageKind,
    SendMessageRequest,
)


class InputOrchestratorService:
    def __init__(self, mode_registry: ModeRegistry) -> None:
        self._mode_registry = mode_registry
        self._qa_task_direction_service = QATaskDirectionService()
        self._qa_task_router_service = QATaskRouterService()

    def orchestrate(self, session: SessionRecord, payload: SendMessageRequest) -> ExecutionRequest:
        raw_content = payload.content or ""
        content = raw_content.strip()
        attachments = list(payload.attachments)
        message_kind = payload.message_kind
        command_name = (payload.command_name or "").strip() or None
        command_args = ""
        hook_results: list[InputHookResult] = []

        detected_command_name, detected_command_args = self._parse_slash_command(content)
        if detected_command_name and message_kind == MessageKind.user_input:
            message_kind = MessageKind.slash_command
            command_name = command_name or detected_command_name
            command_args = detected_command_args
            hook_results.append(
                InputHookResult(
                    hook_key="slash-command-detector",
                    status="applied",
                    message=f"Detected slash command '{command_name}'.",
                    metadata={
                        "command_name": command_name,
                        "command_args_preview": self._preview_text(command_args, 80),
                    },
                )
            )
        elif command_name and detected_command_name == command_name:
            command_args = detected_command_args

        if not content and not attachments and not command_name:
            raise ValueError("Message content, attachments, or command metadata must be provided.")

        if attachments:
            hook_results.append(
                InputHookResult(
                    hook_key="attachment-normalizer",
                    status="applied",
                    message=f"Normalized {len(attachments)} attachment(s) for this input.",
                    metadata={
                        "attachment_count": len(attachments),
                        "attachment_names": [item.name for item in attachments[:5]],
                    },
                )
            )

        normalized_input = " ".join(content.split())
        mode = self._mode_registry.resolve(payload.mode_key or session.mode_key)
        skill_keys = list(dict.fromkeys([*mode.default_skill_keys, *payload.skill_keys]))

        if mode.key == "default":
            detected_task_state = self._qa_task_direction_service.classify(
                message=normalized_input,
                context=payload.context,
            )
            test_route = self._qa_task_router_service.route(detected_task_state)
            test_task_state = {
                "is_test_task": detected_task_state.is_test_task,
                "direction": detected_task_state.direction,
                "confidence": detected_task_state.confidence,
                "needs_direction_selection": detected_task_state.needs_direction_selection,
                "reasons": detected_task_state.reasons,
                "recommended_skills": detected_task_state.recommended_skills,
            }
        else:
            test_task_state = self._build_mode_task_state(mode.key, mode.default_skill_keys)
            test_route = {
                "agent_key": mode.default_agent_key,
                "harness": mode.harness_key,
            }

        for skill_key in test_task_state["recommended_skills"]:
            if skill_key not in skill_keys:
                skill_keys.append(skill_key)
        input_envelope = InputEnvelope(
            raw_content=raw_content,
            normalized_content=normalized_input,
            message_kind=message_kind,
            submit_mode=payload.submit_mode,
            command_name=command_name,
            command_args=command_args,
            attachment_count=len(attachments),
            attachment_names=[item.name for item in attachments[:5]],
            has_text=bool(content),
            has_attachments=bool(attachments),
            source=payload.source,
        )
        routing_decision = self._build_routing_decision(
            session=session,
            payload=payload,
            message_kind=message_kind,
            command_name=command_name,
            command_args=command_args,
            attachment_count=len(attachments),
        )
        harness_flags = self._build_harness_flags(
            existing_flags=payload.context.get("harness_flags", []),
            session=session,
            routing_decision=routing_decision,
            mode_key=mode.key,
            harness_key=str(test_route.get("harness") or mode.harness_key),
        )
        if bool(test_task_state["is_test_task"]):
            for item in [
                "mode_routing",
                f"mode:{mode.key}",
                f"test_direction:{test_task_state['direction']}",
                f"test_harness:{test_route.get('harness', 'base_conversation')}",
            ]:
                if item not in harness_flags:
                    harness_flags.append(item)
        input_summary = self._build_input_summary(
            envelope=input_envelope,
            routing_decision=routing_decision,
            attachments=attachments,
        )
        context = {
            **payload.context,
            "selected_mode": mode.model_dump(mode="python"),
            "input_envelope": input_envelope.model_dump(mode="python"),
            "input_routing": routing_decision.model_dump(mode="python"),
            "test_task_state": {
                "is_test_task": test_task_state["is_test_task"],
                "direction": test_task_state["direction"],
                "confidence": test_task_state["confidence"],
                "needs_direction_selection": test_task_state["needs_direction_selection"],
                "reasons": test_task_state["reasons"],
                "recommended_skills": test_task_state["recommended_skills"],
            },
            "test_route": test_route,
            "attachments": [attachment.model_dump(mode="python") for attachment in attachments],
            "hook_results": [result.model_dump(mode="python") for result in hook_results],
            "harness_flags": harness_flags,
        }
        requested_agent_key = payload.agent_key or session.selected_agent or mode.default_agent_key
        routed_test_agent_key = test_route.get("agent_key") if bool(test_task_state["is_test_task"]) else ""
        if mode.key == "default" and routed_test_agent_key and (not requested_agent_key or requested_agent_key in {"auto", "coordinator"}):
            resolved_agent_key = routed_test_agent_key
        else:
            resolved_agent_key = requested_agent_key or mode.default_agent_key
        orchestration_meta = {
            "mode_key": mode.key,
            "message_kind": message_kind.value,
            "submit_mode": payload.submit_mode,
            "command_name": command_name,
            "command_args": command_args,
            "attachment_count": len(attachments),
            "interrupt_if_busy": payload.interrupt_if_busy,
            "detected_slash_command": bool(detected_command_name),
            "execution_lane": routing_decision.execution_lane,
            "queue_behavior": routing_decision.queue_behavior,
            "interrupt_policy": routing_decision.interrupt_policy,
            "source": payload.source,
            "test_direction": test_task_state["direction"],
            "test_harness": test_route.get("harness", "base_conversation"),
        }

        return ExecutionRequest(
            turn_id=str(uuid4()),
            session_id=session.id,
            user_message=content,
            normalized_input=normalized_input,
            mode_key=mode.key,
            agent_key=resolved_agent_key,
            model_key=payload.model_key or session.preferred_model,
            skill_keys=skill_keys,
            attachments=attachments,
            message_kind=message_kind,
            submit_mode=payload.submit_mode,
            command_name=command_name,
            input_summary=input_summary,
            hook_results=hook_results,
            input_envelope=input_envelope,
            routing_decision=routing_decision,
            orchestration_meta=orchestration_meta,
            context=context,
        )

    def _build_routing_decision(
        self,
        session: SessionRecord,
        payload: SendMessageRequest,
        message_kind: MessageKind,
        command_name: str | None,
        command_args: str,
        attachment_count: int,
    ) -> InputRoutingDecision:
        execution_lane = {
            MessageKind.user_input: "conversation_turn",
            MessageKind.slash_command: "slash_command_turn",
            MessageKind.system_command: "system_command_turn",
            MessageKind.task_notification: "task_notification_turn",
            MessageKind.coordinator_assignment: "coordinator_assignment_turn",
        }[message_kind]
        if payload.interrupt_if_busy:
            queue_behavior = "interrupt_then_retry"
            interrupt_policy = "interrupt_active_turn"
        elif payload.submit_mode in {"queued", "enqueue", "background"}:
            queue_behavior = "enqueue_if_busy"
            interrupt_policy = "wait_for_active_turn"
        else:
            queue_behavior = "reject_when_busy"
            interrupt_policy = "wait_for_active_turn"
        should_stream_response = session.runtime_mode.value != "background"
        return InputRoutingDecision(
            execution_lane=execution_lane,
            queue_behavior=queue_behavior,
            interrupt_policy=interrupt_policy,
            should_persist_user_message=True,
            should_stream_response=should_stream_response,
            expects_model_turn=True,
            metadata={
                "session_mode": session.session_mode.value,
                "runtime_mode": session.runtime_mode.value,
                "command_name": command_name,
                "command_args_preview": self._preview_text(command_args, 80),
                "attachment_count": attachment_count,
            },
        )

    def _build_harness_flags(
        self,
        existing_flags: object,
        session: SessionRecord,
        routing_decision: InputRoutingDecision,
        mode_key: str,
        harness_key: str,
    ) -> list[str]:
        flags: list[str] = []
        for item in existing_flags if isinstance(existing_flags, list) else []:
            text = str(item).strip()
            if text and text not in flags:
                flags.append(text)
        for item in [
            "input_orchestrator",
            "permission_gate",
            "event_sourcing",
            "snapshot_resume",
            "verification",
            f"session_mode:{session.session_mode.value}",
            f"runtime_mode:{session.runtime_mode.value}",
            f"mode:{mode_key}",
            f"harness:{harness_key}",
            f"execution_lane:{routing_decision.execution_lane}",
        ]:
            if item not in flags:
                flags.append(item)
        return flags

    def _build_mode_task_state(self, mode_key: str, recommended_skills: list[str]) -> dict[str, object]:
        return {
            "is_test_task": mode_key != "default",
            "direction": mode_key,
            "confidence": 1.0,
            "needs_direction_selection": False,
            "reasons": [f"Execution is pinned to explicit mode '{mode_key}'."],
            "recommended_skills": list(recommended_skills),
        }

    def _parse_slash_command(self, content: str) -> tuple[str | None, str]:
        if not content.startswith("/"):
            return None, ""
        first_token, _, remainder = content.partition(" ")
        command = first_token[1:].strip().lower()
        return (command or None, remainder.strip())

    def _build_input_summary(
        self,
        envelope: InputEnvelope,
        routing_decision: InputRoutingDecision,
        attachments: Iterable[InputAttachment],
    ) -> str:
        parts: list[str] = [f"kind={envelope.message_kind.value}"]
        parts.append(f"lane={routing_decision.execution_lane}")
        parts.append(f"queue={routing_decision.queue_behavior}")
        if envelope.command_name:
            parts.append(f"command={envelope.command_name}")
        if envelope.command_args:
            parts.append(f"args={self._preview_text(envelope.command_args, 80)}")
        attachment_list = list(attachments)
        if attachment_list:
            names = ", ".join(item.name for item in attachment_list[:3])
            if len(attachment_list) > 3:
                names += ", ..."
            parts.append(f"attachments={len(attachment_list)}[{names}]")
        if envelope.normalized_content:
            parts.append(f"text={self._preview_text(envelope.normalized_content, 120)}")
        return " | ".join(parts)

    def _preview_text(self, value: str, limit: int) -> str:
        preview = " ".join((value or "").split())
        if len(preview) > limit:
            return preview[: limit - 3] + "..."
        return preview
