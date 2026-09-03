from __future__ import annotations

import inspect
import os
import re
from typing import Any, Callable, Dict, Iterable, List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field

from src.action_intents import classify_tool_intent
from src.tool_capabilities import (
    ToolEffect,
    capabilities_for_tool,
)
from src.tool_policy import build_effective_tool_policy


class RequirementBrief(BaseModel):
    """Small, user-safe representation of the requirements inferred for a task.

    This is deliberately a requirements record, not a reasoning transcript.  It
    gives the executor enough durable state to choose tools and verify work
    without exposing private chain-of-thought.
    """

    goal: str
    task_type: str = "chat"
    workflow: str = "answer"
    domains: List[str] = Field(default_factory=list)
    acceptance_criteria: List[str] = Field(default_factory=list)
    constraints: List[str] = Field(default_factory=list)
    assumptions: List[str] = Field(default_factory=list)
    tool_candidates: List[str] = Field(default_factory=list)
    inspection_required: bool = False
    verification_required: bool = True
    high_impact: bool = False
    clarification: Optional[str] = None


def _normalise_text(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def _infer_task_type(
    prompt: str, requested: object, category: str, *, has_workspace: bool = False
) -> str:
    explicit = _normalise_text(requested).lower()
    if explicit and explicit != "chat":
        return explicit
    if category in {"workspace", "shell"}:
        return "coding"
    if re.search(r"\b(?:codebase|repository|repo)\b", prompt, re.I) or re.search(
        r"\b(?:build|create|make|implement|develop|fix|update)\b.{0,30}"
        r"\b(?:website|web app|webapp|app)\b",
        prompt,
        re.I,
    ):
        return "coding"
    if has_workspace and re.search(
        r"\b(?:file|folder|repo|code|source|script|test|bug|config)\b", prompt, re.I
    ) and re.search(
        r"\b(?:create|add|implement|fix|patch|edit|change|update|refactor|build|write)\b",
        prompt,
        re.I,
    ):
        return "coding"
    if category == "research":
        return "research"
    if category == "web":
        return "analysis"
    return "chat"


def extract_requirements(
    prompt: str,
    *,
    task_type: str = "chat",
    context: Optional[Dict[str, Any]] = None,
) -> RequirementBrief:
    """Infer a bounded requirement brief from a natural-language request.

    The extractor uses the existing deterministic intent router and conservative
    defaults.  It never turns an ambiguous request into an irreversible action;
    callers receive one focused clarification instead.
    """

    text = _normalise_text(prompt)
    ctx = context if isinstance(context, dict) else {}
    intent = classify_tool_intent(text)
    inferred_type = _infer_task_type(
        text,
        task_type,
        intent.category,
        has_workspace=bool(_normalise_text(ctx.get("workspace"))),
    )
    domains = [intent.category] if intent.category else []
    if inferred_type == "coding" and "workspace" not in domains:
        domains.append("workspace")

    coding = inferred_type in {
        "coding", "workspace", "shell", "website", "web", "frontend", "app"
    } or "workspace" in domains
    write_request = bool(
        re.search(
            r"\b(?:create|add|implement|fix|patch|edit|change|update|refactor|"
            r"remove|delete|write|build|make)\b",
            text,
            re.IGNORECASE,
        )
    )
    high_impact = bool(
        re.search(
            r"\b(?:delete|remove|destroy|wipe|reset|send|publish|deploy|"
            r"restart|kill|terminate|financial|pay|purchase|admin|token|password)\b",
            text,
            re.IGNORECASE,
        )
    )

    acceptance = ["The requested outcome is produced and reported accurately."]
    constraints: List[str] = []
    assumptions: List[str] = []
    candidates: List[str] = []
    clarification = None
    if coding:
        acceptance.extend(
            [
                "Existing project conventions are preserved.",
                "Relevant existing checks pass, or failures are reported with evidence.",
            ]
        )
        constraints.append("Inspect the active project before changing files.")
        candidates.extend(["get_workspace", "ls", "glob", "grep", "read_file"])
    if write_request and coding:
        candidates.extend(["edit_file", "apply_patch", "write_file"])
    if intent.category == "web":
        candidates.extend(["web_search", "web_fetch"])
        acceptance.append("Time-sensitive claims include source context.")
    if intent.category == "research":
        candidates.append("trigger_research")
    if intent.category in {"calendar", "notes"}:
        candidates.extend(
            {"calendar": ["manage_calendar"], "notes": ["manage_notes"]}[intent.category]
        )
    if intent.category == "email":
        candidates.extend(["list_emails", "read_email", "send_email"])

    workspace = _normalise_text(ctx.get("workspace"))
    if workspace:
        constraints.append(f"Keep file operations inside the active workspace ({workspace}).")
    else:
        assumptions.append("Use the active workspace or explicit paths when available.")

    # A destructive or externally visible request without a concrete target is
    # the one case where guessing is unsafe.  Ask one narrow question, rather
    # than a broad requirements interview.
    if high_impact and not re.search(
        r"\b(?:this|that|the|my|your|named|id|uid|account|file|folder|repo|"
        r"session|email|message|event|service|server)\b",
        text,
        re.IGNORECASE,
    ):
        clarification = "What exact item, account, or environment should this action target?"

    workflow = "answer"
    if coding:
        workflow = "inspect -> plan -> implement -> verify"
    elif intent.category in {"web", "research"}:
        workflow = "retrieve -> synthesize -> cite"
    elif intent.category:
        workflow = "inspect -> act -> verify"

    if high_impact:
        constraints.append("Keep approval and safety gates active for high-impact actions.")
    if not text:
        acceptance = []
        assumptions.append("No actionable request was supplied.")

    # Preserve order while removing duplicate tool hints.
    candidates = list(dict.fromkeys(candidates))
    return RequirementBrief(
        goal=text or "No actionable request",
        task_type=inferred_type,
        workflow=workflow,
        domains=domains,
        acceptance_criteria=acceptance,
        constraints=constraints,
        assumptions=assumptions,
        tool_candidates=candidates,
        inspection_required=coding,
        verification_required=True,
        high_impact=high_impact,
        clarification=clarification,
    )


# Alias with a descriptive name for integrations that call this a "brief".
build_requirement_brief = extract_requirements


class AgentTask(BaseModel):
    """Structured request for the autonomous agent runtime."""

    task_id: Optional[str] = None
    task_type: str = "chat"
    prompt: str = ""
    context: Dict[str, Any] = Field(default_factory=dict)
    tools_allowed: List[str] = Field(default_factory=list)
    require_validation: bool = True

    def ensure_task_id(self) -> str:
        if not self.task_id:
            self.task_id = uuid4().hex
        return self.task_id


class AgentResult(BaseModel):
    """Single result object returned after a task is planned and executed."""

    task_id: str
    status: str
    model_id: str
    summary: str = ""
    actions: List[str] = Field(default_factory=list)
    evidence: List[str] = Field(default_factory=list)
    tool_calls: List[str] = Field(default_factory=list)
    requirement_brief: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None


class ToolRegistry:
    """Registry of callable tools the agent may invoke."""

    def __init__(self):
        self.tools: Dict[str, Callable[..., Any]] = {}

    def register(self, name: str, fn: Callable[..., Any]) -> None:
        self.tools[name] = fn

    def has(self, name: str) -> bool:
        return name in self.tools

    def run(self, name: str, **kwargs: Any) -> Any:
        if name not in self.tools:
            raise ValueError(f"Tool not found: {name}")
        return self.tools[name](**kwargs)

    def list_tools(self) -> List[str]:
        return sorted(self.tools.keys())


class ModelRouter:
    """Selects the best model by task type."""

    def __init__(self, routes: Optional[Dict[str, str]] = None):
        self.routes = routes or {
            "chat": "geplex-ai-core",
            "research": "geplex-ai-core",
            "coding": "geplex-ai-core",
            "analysis": "geplex-ai-core",
            "validation": "geplex-ai-core",
        }

    def choose_model(self, task_type: str) -> str:
        key = str(task_type or "chat").lower()
        return self.routes.get(key, self.routes["chat"])

    def list_routes(self) -> Dict[str, str]:
        return dict(self.routes)


class TaskValidator:
    """Validates an execution result before presenting it to users."""

    def validate(self, result: AgentResult) -> bool:
        if result.status not in {"success", "failed", "needs_clarification", "blocked"}:
            return False
        if result.status == "failed" and not result.error:
            return False
        return True


class AgentMemory:
    """Simple in-memory task store for a session or a user."""

    def __init__(self):
        self.store: Dict[str, Dict[str, Any]] = {}

    def save(self, key: str, value: Dict[str, Any]) -> None:
        self.store[key] = value

    def get(self, key: str, default: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        return self.store.get(key, default)


class AgentOrchestrator:
    """Minimal multi-model agent runtime with tool execution and validation."""

    def __init__(
        self,
        model_router: Optional[ModelRouter] = None,
        tool_registry: Optional[ToolRegistry] = None,
        memory: Optional[AgentMemory] = None,
        validator: Optional[TaskValidator] = None,
    ):
        self.model_router = model_router or ModelRouter()
        self.tool_registry = tool_registry or ToolRegistry()
        self.memory = memory or AgentMemory()
        self.validator = validator or TaskValidator()

    def plan(self, task: AgentTask) -> List[str]:
        brief = extract_requirements(
            task.prompt, task_type=task.task_type, context=task.context
        )
        task_kind = brief.task_type
        request_text = str(task.prompt or "").lower()
        is_website_request = task_kind in {"website", "web", "frontend"} or any(
            phrase in request_text
            for phrase in ("build a website", "create a website", "make a website", "build an app")
        )
        steps = [
            "Understand the request",
            "Create an internal requirement brief",
            f"Classify workflow as {task_kind}",
            "Choose the right model for this task",
            "Inspect relevant context before acting",
            "Validate the outcome",
            "Return a concise result",
        ]
        if task.context.get("workspace"):
            steps.insert(4, "Keep file operations inside the active workspace")
        if task.tools_allowed:
            inspect_index = steps.index("Inspect relevant context before acting")
            steps.insert(inspect_index + 1, "Execute the allowed tool calls")
        if is_website_request:
            steps[2] = "Classify workflow as website delivery"
            inspect_index = steps.index("Inspect relevant context before acting")
            steps[inspect_index + 1:inspect_index + 1] = [
                "Plan pages, interactions, and the smallest complete user flow",
                "Implement the complete runnable website in the workspace",
                "Run existing project checks and fix failures before delivery",
            ]
        return steps

    def build_requirement_brief(self, task: AgentTask) -> RequirementBrief:
        """Return the internal, non-chain-of-thought requirements record."""
        return extract_requirements(
            task.prompt, task_type=task.task_type, context=task.context
        )

    @staticmethod
    def _tool_is_risky(tool_name: str) -> bool:
        """Return whether a known capability must remain behind an approval gate."""
        capabilities = capabilities_for_tool(tool_name)
        if capabilities.known:
            return bool(
                capabilities.effects
                & {
                    ToolEffect.EXTERNAL_SIDE_EFFECT,
                    ToolEffect.DESTRUCTIVE,
                    ToolEffect.ADMIN_CHANGE,
                    ToolEffect.EXECUTE_CODE,
                }
            )
        # Unknown extensions fail closed only for obviously irreversible names;
        # ordinary test doubles and read-only custom tools remain usable.
        return bool(
            re.search(
                r"(?:delete|destroy|wipe|reset|send|publish|deploy|kill|terminate)",
                tool_name,
                re.I,
            )
        )

    @staticmethod
    def _approval_covers(tool_name: str, context: Dict[str, Any]) -> bool:
        if context.get("approval_granted") is True:
            approved = context.get("approved_tools")
            return not approved or tool_name in set(str(v) for v in approved)
        approved = context.get("approved_tools")
        if isinstance(approved, str):
            approved = [approved]
        return isinstance(approved, (list, tuple, set)) and tool_name in {
            str(v) for v in approved
        }

    @staticmethod
    def _path_is_in_workspace(path: object, workspace: object) -> bool:
        if not path or not workspace:
            return True
        try:
            root = os.path.realpath(os.path.expanduser(str(workspace)))
            candidate = str(path)
            if not os.path.isabs(candidate):
                candidate = os.path.join(root, candidate)
            return os.path.commonpath([root, os.path.realpath(candidate)]) == root
        except (OSError, ValueError):
            return False

    def _candidate_tools(self, task: AgentTask, brief: RequirementBrief) -> List[str]:
        """Choose registered tools while preserving explicit caller limits."""
        if task.tools_allowed:
            selected = list(dict.fromkeys(str(name) for name in task.tools_allowed if name))
        else:
            selected = [
                name for name in brief.tool_candidates if self.tool_registry.has(name)
            ]
            # Custom registries often use short phase names.  Recognise those
            # names without guessing arbitrary tools or executing all of them.
            if not selected:
                names = self.tool_registry.list_tools()
                if brief.inspection_required:
                    selected.extend(
                        name
                        for name in names
                        if name in {"get_workspace", "glob", "grep", "ls", "read_file", "file_read"}
                        or re.search(r"(inspect|orient|discover|inventory|scan)(?:_|$)", name, re.I)
                    )
                if brief.task_type == "coding" and re.search(
                    r"\b(?:create|add|implement|fix|patch|edit|change|update|build)\b",
                    brief.goal,
                    re.I,
                ):
                    selected.extend(
                        name
                        for name in names
                        if re.search(r"(write|edit|patch|implement|create|change)", name, re.I)
                    )
                if brief.verification_required:
                    selected.extend(
                        name
                        for name in names
                        if re.search(r"(test|check|verify|validate|lint|build)", name, re.I)
                    )

        # Never edit before an available inspection phase.  This is applied to
        # explicit tool lists too, because ordering is a safety invariant.
        if brief.inspection_required:
            names = self.tool_registry.list_tools()
            inspectors = [
                name
                for name in names
                if name in {"get_workspace", "glob", "grep", "ls", "read_file", "file_read"}
                or re.search(r"(inspect|orient|discover|inventory|scan)(?:_|$)", name, re.I)
            ]
            selected = list(dict.fromkeys(inspectors + selected))
        if brief.inspection_required and re.search(
            r"\b(?:create|add|implement|fix|patch|edit|change|update|refactor|build|"
            r"test|check|verify|validate|lint)\b",
            brief.goal,
            re.I,
        ):
            selected.extend(
                name
                for name in self.tool_registry.list_tools()
                if re.search(r"(test|check|verify|validate|lint|build)(?:_|$)", name, re.I)
            )
            selected = list(dict.fromkeys(selected))
        try:
            max_steps = int(task.context.get("max_steps", 12))
        except (TypeError, ValueError):
            max_steps = 12
        return selected[: max(1, min(max_steps, 20))]

    def _safe_tool_call(
        self, tool_name: str, task: AgentTask, *, policy=None
    ) -> Dict[str, Any]:
        if policy is not None and policy.blocks(tool_name):
            return {
                "tool": tool_name,
                "status": "blocked",
                "reason": policy.reason_for(tool_name),
            }
        if self._tool_is_risky(tool_name) and not self._approval_covers(
            tool_name, task.context
        ):
            return {
                "tool": tool_name,
                "status": "approval_required",
                "reason": "Explicit approval is required before this high-impact action.",
            }
        if tool_name not in self.tool_registry.tools:
            return {"tool": tool_name, "status": "skipped", "reason": "not registered"}
        try:
            # Tool-specific arguments may be supplied in context without
            # forcing every registry callable to accept an identical signature.
            args = {"prompt": task.prompt, "context": task.context}
            tool_args = task.context.get("tool_args", {})
            if isinstance(tool_args, dict) and isinstance(tool_args.get(tool_name), dict):
                args.update(tool_args[tool_name])
            for key in ("path", "content", "old_string", "new_string", "replace_all"):
                if key in task.context and key not in args:
                    args[key] = task.context[key]
            if (
                tool_name in {"write_file", "edit_file", "apply_patch"}
                and not self._path_is_in_workspace(args.get("path"), task.context.get("workspace"))
            ):
                return {
                    "tool": tool_name,
                    "status": "blocked",
                    "reason": "file path is outside the active workspace",
                }
            signature = inspect.signature(self.tool_registry.tools[tool_name])
            accepts_kwargs = any(
                parameter.kind == inspect.Parameter.VAR_KEYWORD
                for parameter in signature.parameters.values()
            )
            if not accepts_kwargs:
                args = {
                    key: value for key, value in args.items()
                    if key in signature.parameters
                }
            required = [
                parameter.name for parameter in signature.parameters.values()
                if parameter.default is inspect.Parameter.empty
                and parameter.kind in {
                    inspect.Parameter.POSITIONAL_ONLY,
                    inspect.Parameter.POSITIONAL_OR_KEYWORD,
                    inspect.Parameter.KEYWORD_ONLY,
                }
                and parameter.name not in args
            ]
            if required:
                return {
                    "tool": tool_name,
                    "status": "error",
                    "error": f"missing required arguments: {', '.join(required)}",
                }
            payload = self.tool_registry.run(tool_name, **args)
            if isinstance(payload, dict):
                payload_error = payload.get("error")
                payload_status = str(payload.get("status") or "").lower()
                exit_code = payload.get("exit_code")
                payload_ok = payload.get("ok")
                if (
                    payload_error
                    or payload_ok is False
                    or payload_status in {"error", "failed"}
                    or (
                        isinstance(exit_code, int)
                        and not isinstance(exit_code, bool)
                        and exit_code != 0
                    )
                ):
                    return {
                        "tool": tool_name,
                        "status": "error",
                        "error": str(
                            payload_error
                            or payload.get("reason")
                            or ("tool reported failure" if payload_ok is False else None)
                            or f"tool returned status {payload_status or exit_code}"
                        ),
                        "payload": payload,
                    }
            return {"tool": tool_name, "status": "ok", "payload": payload}
        except Exception as exc:  # pragma: no cover - defensive runtime path
            return {"tool": tool_name, "status": "error", "error": str(exc)}

    def execute(self, task: AgentTask) -> AgentResult:
        task.task_id = task.ensure_task_id()
        brief = extract_requirements(
            task.prompt, task_type=task.task_type, context=task.context
        )
        selected_model = self.model_router.choose_model(brief.task_type)
        actions: List[str] = [f"selected model {selected_model}"]
        tool_results: List[Dict[str, Any]] = []
        policy = build_effective_tool_policy(
            disabled_tools=task.context.get("disabled_tools"),
            last_user_message=task.prompt,
        )

        if brief.clarification and not task.context.get("clarification_answer"):
            result = AgentResult(
                task_id=task.task_id,
                status="needs_clarification",
                model_id=selected_model,
                summary=brief.clarification,
                actions=actions + ["focused clarification required"],
                evidence=["requirement brief created", "no high-impact tool was run"],
                requirement_brief=brief.model_dump(mode="json"),
            )
            self.memory.save(task.task_id, {
                "task": task.model_dump(mode="json"),
                "result": result.model_dump(mode="json"),
                "plan": self.plan(task),
            })
            return result

        selected_tools = self._candidate_tools(task, brief)
        actions.append("requirement brief created")
        if brief.inspection_required:
            actions.append("inspection precedes workspace changes")
        for tool_name in selected_tools:
            result = self._safe_tool_call(tool_name, task, policy=policy)
            tool_results.append(result)
            actions.append(f"tool:{tool_name}")

        # A failed verification can be repaired once, but execution is bounded
        # and never retries destructive actions automatically.
        failed_verification = any(
            item.get("status") != "ok"
            and re.search(r"(test|check|verify|validate|lint|build)", item["tool"], re.I)
            for item in tool_results
        )
        if failed_verification:
            repair_names = [
                name
                for name in self.tool_registry.list_tools()
                if re.search(r"(fix|repair|patch)(?:_|$)", name, re.I)
                and name not in {item["tool"] for item in tool_results}
            ]
            if not repair_names:
                repair_names = [
                    name
                    for name in self.tool_registry.list_tools()
                    if re.search(r"(fix|repair|patch)(?:_|$)", name, re.I)
                ]
            if repair_names:
                repair = self._safe_tool_call(repair_names[0], task, policy=policy)
                tool_results.append(repair)
                actions.append(f"tool:{repair_names[0]}")
                if repair.get("status") == "ok":
                    verify_name = next(
                        (
                            item["tool"]
                            for item in tool_results
                            if re.search(r"(test|check|verify|validate|lint|build)", item["tool"], re.I)
                        ),
                        None,
                    )
                    if verify_name:
                        retry = self._safe_tool_call(verify_name, task, policy=policy)
                        tool_results.append(retry)
                        actions.append(f"retry:{verify_name}")

        summary = (
            f"Handled '{brief.task_type}' task with model {selected_model}. "
            f"Prompt: {task.prompt[:180]}"
        )
        if tool_results:
            summary += " Tools used: " + ", ".join(item["tool"] for item in tool_results)

        # A verification failure may have been repaired and passed on retry.
        # Judge each tool by its final attempt rather than inventing failure.
        latest_by_tool: Dict[str, Dict[str, Any]] = {}
        for item in tool_results:
            latest_by_tool[item["tool"]] = item
        failed_tools = [
            item for item in latest_by_tool.values() if item.get("status") != "ok"
        ]
        result_status = "failed" if failed_tools else "success"
        result_error = None
        if failed_tools:
            details = "; ".join(
                f"{item['tool']}: {item.get('error') or item.get('reason') or 'execution failed'}"
                for item in failed_tools
            )
            result_error = f"Tool execution failed: {details}"
            actions.append("tool execution failure detected")

        result = AgentResult(
            task_id=task.task_id,
            status=result_status,
            model_id=selected_model,
            summary=summary,
            actions=actions,
            evidence=[
                "requirement brief created",
                f"task_type={brief.task_type}",
                f"model={selected_model}",
                *[
                    f"tool={item['tool']};status={item.get('status')}"
                    for item in tool_results
                ],
            ],
            tool_calls=[item["tool"] for item in tool_results],
            requirement_brief=brief.model_dump(mode="json"),
            error=result_error,
        )

        if task.require_validation:
            validation_ok = self.validator.validate(result)
            if not validation_ok:
                result.status = "failed"
                result.error = "Validation failed before final response"
            else:
                result.evidence.append("validation=passed")

        self.memory.save(task.task_id, {
            "task": task.model_dump(mode="json"),
            "result": result.model_dump(mode="json"),
            "plan": self.plan(task),
        })
        return result


def register_default_tools(registry: ToolRegistry) -> ToolRegistry:
    """Registers a small safe tool set used by the default agent runtime."""

    def tool_search(prompt: str, context: Optional[Dict[str, Any]] = None, **_: Any) -> Dict[str, Any]:
        return {
            "type": "search",
            "query": prompt,
            "results": [{"title": "Search stub", "snippet": "Agent search is enabled and ready."}],
            "context": context or {},
        }

    def tool_file_read(path: str, **_: Any) -> Dict[str, Any]:
        try:
            with open(path, "r", encoding="utf-8") as handle:
                data = handle.read()
            return {"type": "file_read", "path": path, "content": data[:4000]}
        except Exception as exc:
            return {"type": "file_read", "path": path, "error": str(exc)}

    def tool_file_write(path: str, content: str, **_: Any) -> Dict[str, Any]:
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(content)
        return {"type": "file_write", "path": path, "bytes_written": len(content.encode("utf-8"))}

    def tool_echo(prompt: str, **_: Any) -> Dict[str, Any]:
        return {"type": "echo", "prompt": prompt}

    registry.register("search", tool_search)
    registry.register("file_read", tool_file_read)
    registry.register("file_write", tool_file_write)
    registry.register("echo", tool_echo)
    return registry


def build_default_orchestrator() -> AgentOrchestrator:
    return AgentOrchestrator(
        model_router=ModelRouter(),
        tool_registry=register_default_tools(ToolRegistry()),
        memory=AgentMemory(),
        validator=TaskValidator(),
    )
