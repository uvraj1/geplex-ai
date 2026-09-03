from src.agent_runtime import (
    AgentOrchestrator,
    AgentTask,
    ModelRouter,
    ToolRegistry,
    extract_requirements,
    register_default_tools,
)


def test_default_model_router_uses_geplex_core():
    router = ModelRouter()
    assert router.choose_model("chat") == "geplex-ai-core"
    assert router.choose_model("coding") == "geplex-ai-core"
    assert router.choose_model("unknown") == "geplex-ai-core"


def test_orchestrator_executes_allowed_tools_and_returns_result():
    registry = register_default_tools(ToolRegistry())
    orchestrator = AgentOrchestrator(model_router=ModelRouter(), tool_registry=registry)

    task = AgentTask(
        task_type="analysis",
        prompt="Review the latest deployment checklist and identify risks.",
        tools_allowed=["search", "echo"],
    )

    result = orchestrator.execute(task)

    assert result.task_id
    assert result.model_id == "geplex-ai-core"
    assert result.status == "success"
    assert "search" in result.tool_calls
    assert "echo" in result.tool_calls
    assert "selected model geplex-ai-core" in result.actions[0]


def test_plan_lists_execution_steps():
    registry = register_default_tools(ToolRegistry())
    orchestrator = AgentOrchestrator(model_router=ModelRouter(), tool_registry=registry)

    task = AgentTask(task_type="research", prompt="Map the launch plan", tools_allowed=["search"])
    steps = orchestrator.plan(task)

    assert "Execute the allowed tool calls" in steps
    assert "Validate the outcome" in steps


def test_orchestrator_fails_when_a_requested_tool_is_not_registered():
    orchestrator = AgentOrchestrator(tool_registry=ToolRegistry())

    result = orchestrator.execute(
        AgentTask(prompt="Inspect the deployment", tools_allowed=["missing_tool"])
    )

    assert result.status == "failed"
    assert result.error == "Tool execution failed: missing_tool: not registered"
    assert "tool=missing_tool;status=skipped" in result.evidence


def test_orchestrator_fails_when_a_tool_raises():
    registry = ToolRegistry()

    def failing_tool(**_kwargs):
        raise RuntimeError("backend unavailable")

    registry.register("failing_tool", failing_tool)
    orchestrator = AgentOrchestrator(tool_registry=registry)

    result = orchestrator.execute(
        AgentTask(prompt="Run the diagnostic", tools_allowed=["failing_tool"])
    )

    assert result.status == "failed"
    assert result.error == (
        "Tool execution failed: failing_tool: backend unavailable"
    )
    assert "tool=failing_tool;status=error" in result.evidence


def test_orchestrator_fails_when_a_tool_returns_an_error_payload():
    registry = ToolRegistry()
    registry.register(
        "reported_failure",
        lambda **_kwargs: {"error": "remote service rejected the request"},
    )
    orchestrator = AgentOrchestrator(tool_registry=registry)

    result = orchestrator.execute(
        AgentTask(prompt="Call the remote service", tools_allowed=["reported_failure"])
    )

    assert result.status == "failed"
    assert result.error == (
        "Tool execution failed: reported_failure: "
        "remote service rejected the request"
    )


def test_orchestrator_passes_tool_specific_context_arguments():
    registry = ToolRegistry()
    registry.register("read", lambda path: {"content": f"read:{path}"})
    orchestrator = AgentOrchestrator(tool_registry=registry)

    result = orchestrator.execute(
        AgentTask(
            task_type="coding",
            prompt="Inspect the entry point",
            tools_allowed=["read"],
            context={"tool_args": {"read": {"path": "src/main.py"}}},
        )
    )

    assert result.status == "success"
    assert result.error is None


def test_coding_plan_keeps_workspace_operations_ordered():
    orchestrator = AgentOrchestrator()

    steps = orchestrator.plan(
        AgentTask(task_type="coding", prompt="Fix the project", context={"workspace": "C:/project"})
    )

    assert steps.index("Inspect relevant context before acting") < steps.index(
        "Validate the outcome"
    )
    assert "Keep file operations inside the active workspace" in steps


def test_website_request_plan_is_end_to_end():
    steps = AgentOrchestrator().plan(
        AgentTask(prompt="Build a website for my portfolio", context={"workspace": "C:/project"})
    )

    assert "Classify workflow as website delivery" in steps
    assert "Plan pages, interactions, and the smallest complete user flow" in steps
    assert "Implement the complete runnable website in the workspace" in steps
    assert "Run existing project checks and fix failures before delivery" in steps


def test_requirement_extraction_creates_bounded_coding_brief():
    brief = extract_requirements(
        "Fix the failing login test in this repo and run the checks",
        context={"workspace": "C:/project"},
    )

    assert brief.task_type == "coding"
    assert brief.goal.startswith("Fix the failing login test")
    assert brief.inspection_required is True
    assert "Inspect the active project before changing files." in brief.constraints
    assert any("checks pass" in item for item in brief.acceptance_criteria)
    assert "write_file" in brief.tool_candidates


def test_high_impact_ambiguous_request_asks_one_focused_question():
    result = AgentOrchestrator().execute(AgentTask(prompt="Delete everything"))

    assert result.status == "needs_clarification"
    assert result.tool_calls == []
    assert "exact item" in result.summary
    assert "chain" not in result.summary.lower()


def test_workspace_inspection_precedes_file_change():
    calls = []
    registry = ToolRegistry()
    registry.register("inspect_project", lambda **_: calls.append("inspect") or {"ok": True})
    registry.register("write_file", lambda path, content, **_: calls.append("write") or {"ok": True})
    orchestrator = AgentOrchestrator(tool_registry=registry)

    result = orchestrator.execute(
        AgentTask(
            task_type="coding",
            prompt="Create the missing config file in this repo",
            tools_allowed=["write_file"],
            context={
                "workspace": "C:/project",
                "tool_args": {"write_file": {"path": "config.json", "content": "{}"}},
            },
        )
    )

    assert result.status == "success"
    assert calls == ["inspect", "write"]


def test_approval_and_guide_only_policy_block_actions():
    calls = []
    registry = ToolRegistry()
    registry.register("delete_email", lambda **_: calls.append("delete") or {"ok": True})
    orchestrator = AgentOrchestrator(tool_registry=registry)

    approval_result = orchestrator.execute(
        AgentTask(prompt="delete that email", tools_allowed=["delete_email"])
    )
    guide_result = orchestrator.execute(
        AgentTask(prompt="Do not use any tools; delete that email", tools_allowed=["delete_email"])
    )

    assert calls == []
    assert approval_result.status == "failed"
    assert "approval is required" in approval_result.error.lower()
    assert guide_result.status == "failed"
    assert "forbade tool use" in guide_result.error.lower()


def test_failed_check_is_repaired_and_verified_once():
    calls = []
    registry = ToolRegistry()

    def run_tests(**_):
        calls.append("test")
        return {"ok": len([call for call in calls if call == "test"]) > 1}

    registry.register("inspect_project", lambda **_: calls.append("inspect") or {"ok": True})
    registry.register("run_tests", run_tests)
    registry.register("fix_project", lambda **_: calls.append("fix") or {"ok": True})
    orchestrator = AgentOrchestrator(tool_registry=registry)

    result = orchestrator.execute(
        AgentTask(
            task_type="coding",
            prompt="Run the tests and verify the project",
        )
    )

    assert result.status == "success"
    assert calls == ["inspect", "test", "fix", "test"]
    assert "retry:run_tests" in result.actions
