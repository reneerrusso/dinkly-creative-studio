from __future__ import annotations

import time

from app.backend.services.agent_task_service import AgentTaskService
from app.backend.services.dinkly_agent_runtime import DinklyAgent
from app.backend.services.repository_service import RepositoryError, RepositoryService


def test_natural_language_planner_routes_visible_work_to_one_agent(repository: RepositoryService) -> None:
    agent = DinklyAgent(repository)

    assert agent.plan_task("Give me five cozy comic ideas.")["task_type"] == "generate_concepts"
    assert agent.plan_task("Generate COFFEE / COFFEE WITH YOU.")["task_type"] == "generate_comic"
    assert agent.plan_task("Make Candidate C again with Nano Banana Pro.")["task_type"] == "repair_comic"
    assert agent.plan_task("Stop giving me couch concepts.")["task_type"] == "feedback"
    assert agent.plan_task("What have you learned this week?")["task_type"] == "brain_query"


def test_story_library_selection_is_preserved_in_agent_task(repository: RepositoryService) -> None:
    tasks = AgentTaskService(repository)
    agent = DinklyAgent(repository, tasks=tasks)

    response = agent.receive_instruction(
        channel="web",
        message="Generate WALKS / WALKS WITH YOU.",
        user_id="owner",
        thread_id="web-story-test",
        extra_context={"story_id": "story-everyday-routines-walks"},
    )

    saved = tasks.get(response["task"]["id"])
    assert saved["task_type"] == "generate_comic"
    assert saved["context"]["story_id"] == "story-everyday-routines-walks"
    assert "coffee" not in saved["user_instruction"].lower()


def test_workspace_and_task_event_feed_restore_active_work(repository: RepositoryService) -> None:
    tasks = AgentTaskService(repository)
    agent = DinklyAgent(repository, tasks=tasks)
    created = agent.receive_instruction(
        channel="web",
        message="Generate WALKS / WALKS WITH YOU.",
        user_id="owner",
        thread_id="web-default",
    )["task"]
    running = tasks.claim_next()
    assert running is not None
    agent.emit_event(running, "generating", "Generating Candidate B.", stage="generate", status="active", candidate="B", completed=1, total=4)

    workspace = agent.workspace()
    events = agent.task_events(created["id"])

    assert workspace["current_task"]["id"] == created["id"]
    assert workspace["current_task"]["status"] == "running"
    assert events[-1]["details"]["candidate"] == "B"
    assert events[-1]["details"]["total"] == 4


def test_cancelled_task_does_not_block_next_queued_task(repository: RepositoryService) -> None:
    tasks = AgentTaskService(repository)
    agent = DinklyAgent(repository, tasks=tasks)
    first, _ = tasks.create_task(source_channel="web", source_thread_id="web-default", user_instruction="Generate COFFEE", task_type="custom")
    second, _ = tasks.create_task(source_channel="web", source_thread_id="web-default", user_instruction="Generate PARTY", task_type="custom")

    def invoke(task):
        if task["id"] == first["id"]:
            agent.request_cancellation(task["id"])
            agent._checkpoint(task["id"], "Candidate 2 of 4")
        return agent.complete_task(task, {"message": "Second task complete"})

    agent.invoke_tool = invoke  # type: ignore[method-assign]
    cancelled = agent.start_run()
    completed = agent.start_run()
    assert cancelled and cancelled["status"] == "cancelled"
    assert completed and completed["id"] == second["id"] and completed["status"] == "completed"
    assert tasks.peek_next() is None
    event_types = [event.get("details", {}).get("event_type") for event in agent.task_events(second["id"])]
    assert "next_task_started" in event_types


def test_task_timeout_uses_safe_cancellation(repository: RepositoryService) -> None:
    tasks = AgentTaskService(repository)
    agent = DinklyAgent(repository, tasks=tasks)
    agent.visual.update_settings({"maximum_task_runtime_seconds": 0.02})
    task, _ = tasks.create_task(source_channel="web", source_thread_id="web-default", user_instruction="Slow task", task_type="custom")

    def invoke(running):
        time.sleep(0.05)
        agent._checkpoint(running["id"], "After slow safe step")

    agent.invoke_tool = invoke  # type: ignore[method-assign]
    result = agent.start_run()
    assert result and result["id"] == task["id"]
    assert result["status"] == "cancelled"
    assert "Maximum runtime" in result["cancellation_reason"]


def test_completed_source_task_is_removed_after_comic_approval(repository: RepositoryService) -> None:
    tasks = AgentTaskService(repository)
    agent = DinklyAgent(repository, tasks=tasks)
    source = agent.receive_instruction(
        channel="web",
        message="Generate PARTY / PARTY WITH YOU.",
        user_id="owner",
        thread_id="web-default",
    )["task"]
    tasks.complete(
        source["id"],
        {"message": "PARTY is ready."},
        run_ids=["generation-123456789abc"],
        waiting_for_human=True,
    )
    approved = {"id": "generation-123456789abc", "status": "approved"}

    agent._complete_source_generation_task("generation-123456789abc", approved)

    assert tasks.get(source["id"])["status"] == "completed"
    assert agent.workspace()["current_task"] is None
    event_types = [event.get("details", {}).get("event_type") for event in agent.task_events(source["id"])]
    assert "comic_approved" in event_types
    assert "task_completed" in event_types


def test_context_continues_from_web_to_slack_without_repeating_ids(repository: RepositoryService) -> None:
    tasks = AgentTaskService(repository)
    agent = DinklyAgent(repository, tasks=tasks)
    first = agent.receive_instruction(
        channel="web",
        message="Give me 5 concepts.",
        user_id="owner",
        thread_id="web-default",
    )["task"]
    tasks.complete(
        first["id"],
        {"message": "I made 5.", "concept_ids": ["concept-a", "concept-b", "concept-c", "concept-d", "concept-e"]},
        artifact_ids=["concept-a", "concept-b", "concept-c", "concept-d", "concept-e"],
        waiting_for_human=True,
    )

    follow_up = agent.receive_instruction(
        channel="slack",
        message="I like number 4.",
        user_id="UOWNER",
        thread_id="slack-thread-2",
        channel_id="C1",
    )["task"]

    assert follow_up["task_type"] == "feedback"
    assert follow_up["context"]["recent_task_id"] == first["id"]
    assert follow_up["context"]["recent_artifact_ids"] == ["concept-d"]


def test_context_continues_from_slack_back_to_web(repository: RepositoryService) -> None:
    tasks = AgentTaskService(repository)
    agent = DinklyAgent(repository, tasks=tasks)
    first = agent.receive_instruction(
        channel="slack",
        message="Give me 3 concepts.",
        user_id="UOWNER",
        thread_id="slack-thread-1",
        channel_id="C1",
    )["task"]
    tasks.complete(
        first["id"],
        {"message": "I made 3.", "concept_ids": ["concept-a", "concept-b", "concept-c"]},
        artifact_ids=["concept-a", "concept-b", "concept-c"],
        waiting_for_human=True,
    )

    follow_up = agent.receive_instruction(
        channel="web",
        message="Give me more like this.",
        user_id="owner",
        thread_id="new-web-thread",
    )["task"]

    assert follow_up["task_type"] == "feedback"
    assert follow_up["context"]["recent_task_id"] == first["id"]
    assert follow_up["context"]["recent_artifact_ids"] == ["concept-a", "concept-b", "concept-c"]


def test_slack_provider_and_budget_failures_remain_saved_in_shared_history(repository: RepositoryService) -> None:
    class FailingGeneration:
        def __init__(self, message: str) -> None:
            self.message = message

        def build_brief(self, _request):
            return {
                "story_brief": {
                    "format": "x-with-you",
                    "title_left": "COFFEE",
                    "title_right": "COFFEE WITH YOU",
                    "left_character": "boy",
                    "left_action": "Dinko waits beside a coffee machine.",
                    "left_setting": "cafe",
                    "left_props": ["coffee machine"],
                    "left_emotion": "neutral",
                    "right_characters": ["boy", "girl"],
                    "right_action": "Dinko and Dinka share coffee.",
                    "right_setting": "cafe",
                    "right_props": ["coffee machine", "two chairs"],
                    "right_emotion": "warm",
                    "shared_environment": "One continuous cafe.",
                    "environmental_contrast": "Together changes the feeling.",
                    "background_color": "warm cream",
                    "accent_color": "muted brown",
                    "camera_angle": "medium straight-on",
                    "execution_risks": [],
                    "emotional_insight": "Ordinary coffee is better together.",
                    "brand_sensitive": False,
                }
            }

        def start(self, _request):
            raise RepositoryError(self.message)

        def history(self):
            return []

    for index, error in enumerate(
        (
            "Image provider connection failed safely.",
            "Nano Banana Pro exceeds the automatic cost threshold. Use Pro, Use Balanced, or Cancel.",
        )
    ):
        tasks = AgentTaskService(repository)
        agent = DinklyAgent(repository, tasks=tasks, generation=FailingGeneration(error))  # type: ignore[arg-type]
        response = agent.receive_instruction(
            channel="slack",
            message="Generate COFFEE / COFFEE WITH YOU.",
            user_id="UOWNER",
            thread_id=f"slack-failure-{index}",
            channel_id="C1",
        )
        failed = agent.start_run()
        assert failed is not None
        assert failed["id"] == response["task"]["id"]
        assert failed["status"] == "failed"
        assert error in failed["error"]
        assert any(error in item["message"] for item in tasks.conversation(thread_id=f"slack-failure-{index}"))


def test_scheduled_concept_work_uses_automatic_budget_source(repository: RepositoryService) -> None:
    class FakeConcepts:
        def local_date(self):
            from datetime import date

            return date(2026, 8, 7)

        def has_primary_batch(self, _day):
            return False

        def generate_daily_concept_batch(self, **kwargs):
            assert kwargs["source"] == "scheduled"
            return {
                "status": "skipped",
                "message": "Paid model calls are disabled for automatic generation.",
                "problems": ["Paid model calls are disabled for automatic generation."],
                "run": {"id": "run-scheduled"},
            }

        def list_concepts(self):
            return []

    tasks = AgentTaskService(repository)
    task, _ = tasks.create_task(
        source_channel="scheduled",
        source_thread_id="daily-2026-08-07",
        user_instruction="Create today's scheduled concepts",
        task_type="generate_concepts",
    )
    running = tasks.claim_next()
    assert running is not None
    agent = DinklyAgent(repository, tasks=tasks, concepts=FakeConcepts())  # type: ignore[arg-type]

    completed = agent.invoke_tool(running)

    assert completed["status"] == "completed"
    assert completed["result"]["skipped"] is True
    assert completed["run_ids"] == ["run-scheduled"]
