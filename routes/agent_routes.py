from fastapi import APIRouter

from src.agent_runtime import AgentTask, AgentOrchestrator, build_default_orchestrator


def setup_agent_routes() -> APIRouter:
    router = APIRouter(prefix="/api/agent", tags=["agent"])
    orchestrator: AgentOrchestrator = build_default_orchestrator()

    @router.get("/status")
    async def get_agent_status():
        return {
            "default_model": orchestrator.model_router.choose_model("chat"),
            "models": orchestrator.model_router.list_routes(),
            "tools": orchestrator.tool_registry.list_tools(),
        }

    @router.post("/plan")
    async def plan_agent_task(task: AgentTask):
        return {
            "task_id": task.ensure_task_id(),
            "plan": orchestrator.plan(task),
            "selected_model": orchestrator.model_router.choose_model(task.task_type),
        }

    @router.post("/run")
    async def run_agent_task(task: AgentTask):
        result = orchestrator.execute(task)
        return result.model_dump(mode="json")

    return router
