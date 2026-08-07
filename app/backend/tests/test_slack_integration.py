from __future__ import annotations

import hashlib
import hmac
import json

import pytest

from app.backend.models.dinkly_agent import SlackConnectRequest
from app.backend.services.agent_channels import SlackAgentChannel, public_asset_url
from app.backend.services.agent_task_service import AgentTaskService
from app.backend.services.repository_service import RepositoryError, RepositoryService
from app.backend.services.slack_service import SlackService, SlackSignatureVerifier


class RecordingTransport:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    def call(self, method: str, payload: dict) -> dict:
        self.calls.append((method, payload))
        if method == "auth.test":
            return {"ok": True, "team_id": "T1", "team": "DINKLY", "user_id": "B1", "user": "DINKLY"}
        if method == "apps.connections.open":
            return {"ok": True, "url": "wss://wss-primary.slack.com/link/test"}
        return {"ok": True, "ts": f"1000.{len(self.calls)}"}


class FailingMessageTransport(RecordingTransport):
    def call(self, method: str, payload: dict) -> dict:
        if method == "chat.postMessage":
            raise RepositoryError("Slack API error: channel_not_found")
        return super().call(method, payload)


class Receiver:
    def __init__(self, tasks: AgentTaskService) -> None:
        self.tasks = tasks
        self.instructions: list[dict] = []
        self.approvals: list[dict] = []

    def instruction(self, **kwargs):
        self.instructions.append(kwargs)
        task, created = self.tasks.create_task(
            source_channel="slack",
            source_thread_id=kwargs["thread_id"],
            source_user_id=kwargs["user_id"],
            source_message_id=kwargs.get("source_message_id"),
            user_instruction=kwargs["message"],
            task_type="generate_comic" if "generate" in kwargs["message"].lower() else "feedback",
            context={"slack_channel_id": kwargs.get("channel_id")},
        )
        return {"task": task, "created": created}

    def approval(self, **kwargs):
        self.approvals.append(kwargs)
        task, created = self.tasks.create_task(
            source_channel="slack",
            source_thread_id=kwargs["source_thread_id"],
            source_user_id=kwargs["user_id"],
            user_instruction=f"{kwargs['action']} {kwargs['item_id']}",
            task_type="approval",
            context=kwargs,
        )
        return {"task": task, "created": created}


def configured_slack(repository: RepositoryService):
    tasks = AgentTaskService(repository)
    receiver = Receiver(tasks)
    transport = RecordingTransport()
    service = SlackService(
        repository,
        tasks,
        receiver.instruction,
        receiver.approval,
        transport_factory=lambda _token: transport,
    )
    status = service.connect(
        SlackConnectRequest(
            bot_token="xoxb-test-token-123",
            signing_secret="signing-secret-123",
            mode="events_api",
            default_channel="CDEFAULT",
            allowed_users=["UOWNER"],
        )
    )
    assert status["connected"] is True
    return service, tasks, receiver, transport


def test_slack_not_configured_is_truthful(repository: RepositoryService) -> None:
    tasks = AgentTaskService(repository)
    receiver = Receiver(tasks)
    service = SlackService(repository, tasks, receiver.instruction, receiver.approval)

    assert service.status()["connected"] is False
    assert service.status()["connection_status"] == "Not connected"


def test_socket_mode_validates_bot_and_app_tokens(repository: RepositoryService) -> None:
    tasks = AgentTaskService(repository)
    receiver = Receiver(tasks)
    transport = RecordingTransport()
    service = SlackService(
        repository,
        tasks,
        receiver.instruction,
        receiver.approval,
        transport_factory=lambda _token: transport,
    )

    status = service.connect(
        SlackConnectRequest(
            bot_token="xoxb-test-token-123",
            signing_secret="signing-secret-123",
            app_token="xapp-test-token-123",
            mode="socket_mode",
            allowed_users=["UOWNER"],
        )
    )

    assert [method for method, _payload in transport.calls] == ["auth.test", "apps.connections.open"]
    assert status["connected"] is True
    assert status["workspace_name"] == "DINKLY"
    assert status["bot_name"] == "DINKLY"
    assert status["socket_mode_configured"] is True
    assert status["socket_mode_status"] == "Verified — worker connecting automatically"
    assert status["tls_status"] == "Connected"
    assert status["slack_api_status"] == "Connected"


def test_socket_mode_reports_missing_app_token(repository: RepositoryService) -> None:
    tasks = AgentTaskService(repository)
    receiver = Receiver(tasks)
    service = SlackService(
        repository,
        tasks,
        receiver.instruction,
        receiver.approval,
        transport_factory=lambda _token: RecordingTransport(),
    )

    with pytest.raises(RepositoryError, match="Missing environment variable: SLACK_APP_TOKEN"):
        service.connect(
            SlackConnectRequest(
                bot_token="xoxb-test-token-123",
                signing_secret="signing-secret-123",
                mode="socket_mode",
                allowed_users=["UOWNER"],
            )
        )

    assert service.status()["connected"] is False


def test_real_test_message_marks_delivery_metadata(repository: RepositoryService) -> None:
    service, _tasks, _receiver, transport = configured_slack(repository)

    status = service.test_message()

    message = next(payload for method, payload in transport.calls if method == "chat.postMessage")
    assert message["channel"] == "CDEFAULT"
    assert message["text"] == "DINKLY Agent is connected."
    assert status["connected"] is True
    assert status["last_message_sent"]


def test_real_test_message_failure_clears_connected_state(repository: RepositoryService) -> None:
    tasks = AgentTaskService(repository)
    receiver = Receiver(tasks)
    transport = FailingMessageTransport()
    service = SlackService(repository, tasks, receiver.instruction, receiver.approval, transport_factory=lambda _token: transport)
    service.connect(SlackConnectRequest(bot_token="xoxb-test-token-123", signing_secret="signing-secret-123", default_channel="CDEFAULT", allowed_users=["UOWNER"]))

    with pytest.raises(RepositoryError, match="channel_not_found"):
        service.test_message()

    assert service.status()["connected"] is False
    assert service.status()["connection_status"].startswith("Error — test message failed")


def test_slack_signature_validation_and_replay_window() -> None:
    body = b'{"type":"event_callback"}'
    timestamp = "1000"
    secret = "signing-secret"
    signature = "v0=" + hmac.new(secret.encode(), f"v0:{timestamp}:".encode() + body, hashlib.sha256).hexdigest()
    verifier = SlackSignatureVerifier(secret, clock=lambda: 1000)

    assert verifier.verify(timestamp, signature, body) is True
    assert verifier.verify(timestamp, "v0=bad", body) is False
    assert SlackSignatureVerifier(secret, clock=lambda: 1400).verify(timestamp, signature, body) is False


def test_slack_dm_and_mention_share_threaded_agent_inbox(repository: RepositoryService) -> None:
    service, tasks, receiver, transport = configured_slack(repository)
    dm = service.receive_event(
        {
            "event_id": "Ev-DM",
            "event": {"type": "message", "channel_type": "im", "channel": "D1", "user": "UOWNER", "ts": "111.1", "text": "Generate COFFEE / COFFEE WITH YOU."},
        }
    )
    mention = service.receive_event(
        {
            "event_id": "Ev-MENTION",
            "event": {"type": "app_mention", "channel": "C1", "user": "UOWNER", "ts": "222.1", "thread_ts": "200.1", "text": "<@B1> stop giving me couch concepts"},
        }
    )

    assert dm["task"]["source_thread_id"] == "111.1"
    assert mention["task"]["source_thread_id"] == "200.1"
    assert receiver.instructions[1]["message"] == "stop giving me couch concepts"
    status_calls = [payload for method, payload in transport.calls if method == "chat.postMessage"]
    assert any(call.get("thread_ts") == "111.1" for call in status_calls)
    assert any(call.get("thread_ts") == "200.1" for call in status_calls)
    assert tasks.get(dm["task"]["id"])["context"]["slack_status_ts"]


def test_conversational_comic_message_is_acknowledged_and_handed_to_shared_story_brief(repository: RepositoryService) -> None:
    service, _tasks, receiver, transport = configured_slack(repository)

    result = service.receive_event(
        {
            "event_id": "Ev-WINGS",
            "event": {
                "type": "message",
                "channel_type": "im",
                "channel": "D1",
                "user": "UOWNER",
                "ts": "777.1",
                "text": "create me a comic of eating wings and eating wings with you",
            },
        }
    )

    assert result["ok"] is True
    assert receiver.instructions[0]["extra_context"]["left_title"] == "EATING WINGS."
    assert receiver.instructions[0]["extra_context"]["right_title"] == "EATING WINGS WITH YOU."
    assert receiver.instructions[0]["extra_context"]["story_brief"]["left_emotion"].endswith("never happy.")
    assert receiver.instructions[0]["extra_context"]["slack_ack_pending"] is True
    assert result["task"]["context"]["slack_ack_pending"] is False
    messages = [payload for method, payload in transport.calls if method == "chat.postMessage"]
    assert messages[-1]["text"] == "Task received! On it."
    open_button = messages[-1]["blocks"][1]["elements"][0]
    assert open_button["text"]["text"] == "See task running"
    assert open_button["url"].endswith(f"/agent/tasks/{result['task']['id']}")


def test_slack_cancel_current_task_updates_shared_web_state(repository: RepositoryService) -> None:
    service, tasks, _receiver, transport = configured_slack(repository)
    task, _ = tasks.create_task(
        source_channel="slack",
        source_thread_id="111.1",
        source_user_id="UOWNER",
        user_instruction="Generate COFFEE / COFFEE WITH YOU.",
        task_type="generate_comic",
    )
    tasks.claim_next()
    service.cancellation_receiver = lambda task_id, **kwargs: {
        "task": tasks.request_cancellation(task_id, reason=kwargs.get("reason", "Slack"))[0],
        "message": "Cancellation requested.",
    }
    result = service.receive_event(
        {
            "event_id": "Ev-CANCEL",
            "event": {"type": "message", "channel_type": "im", "channel": "D1", "user": "UOWNER", "ts": "111.2", "thread_ts": "111.1", "text": "cancel this task"},
        }
    )
    assert result["task"]["id"] == task["id"]
    assert tasks.get(task["id"])["status"] == "cancellation_requested"
    messages = [payload["text"] for method, payload in transport.calls if method == "chat.postMessage"]
    assert any("Cancellation requested" in message for message in messages)


def test_duplicate_and_unauthorized_slack_events_do_not_create_paid_work(repository: RepositoryService) -> None:
    service, tasks, _receiver, transport = configured_slack(repository)
    event = {
        "event_id": "Ev-DUP",
        "event": {"type": "message", "channel_type": "im", "channel": "D1", "user": "UOWNER", "ts": "333.1", "text": "Generate a comic"},
    }
    service.receive_event(event)
    assert service.receive_event(event)["duplicate"] is True
    before = len(tasks.list_tasks())
    denied = service.receive_event(
        {
            "event_id": "Ev-DENIED",
            "event": {"type": "message", "channel_type": "im", "channel": "D2", "user": "UNAUTHORIZED", "ts": "444.1", "text": "Generate Pro comic"},
        }
    )
    assert denied["unauthorized"] is True
    assert len(tasks.list_tasks()) == before
    assert any("isn't available" in payload.get("text", "") for method, payload in transport.calls if method == "chat.postMessage")


def test_message_timestamp_is_idempotency_key_when_slack_event_id_is_missing(repository: RepositoryService) -> None:
    service, tasks, _receiver, _transport = configured_slack(repository)
    event = {
        "event": {
            "type": "message",
            "channel_type": "im",
            "channel": "D1",
            "user": "UOWNER",
            "ts": "999.1",
            "text": "make coffee and coffee with you",
        }
    }

    service.receive_event(event)
    assert service.receive_event(event) == {"ok": True, "duplicate": True}
    assert len(tasks.list_tasks()) == 1


def test_comic_button_rejects_candidate_not_linked_to_slack_task(repository: RepositoryService) -> None:
    service, tasks, _receiver, _transport = configured_slack(repository)
    task, _ = tasks.create_task(
        source_channel="slack",
        source_thread_id="500.1",
        source_user_id="UOWNER",
        user_instruction="Generate PARTY / PARTY WITH YOU.",
        task_type="generate_comic",
        context={"slack_channel_id": "C1"},
    )
    tasks.complete(
        task["id"],
        {"recommended_candidate_id": "candidate-b"},
        run_ids=["generation-1"],
        waiting_for_human=True,
    )

    with pytest.raises(RepositoryError, match="recommended candidate"):
        service.receive_interaction(
            {
                "trigger_id": "secure-trigger",
                "team": {"id": "T1"},
                "user": {"id": "UOWNER"},
                "channel": {"id": "C1"},
                "message": {"ts": "600.1", "thread_ts": "500.1"},
                "actions": [{
                    "action_id": "dinkly_approve",
                    "value": json.dumps({
                        "item_type": "comic",
                        "item_id": "generation-1",
                        "task_id": task["id"],
                        "candidate_id": "candidate-a",
                        "workspace_id": "T1",
                    }),
                }],
            }
        )


def test_slack_approval_pass_and_feedback_buttons_use_same_action_receiver(repository: RepositoryService) -> None:
    service, _tasks, receiver, _transport = configured_slack(repository)
    for index, action_id in enumerate(("dinkly_approve", "dinkly_pass", "dinkly_more_like_this"), start=1):
        service.receive_interaction(
            {
                "trigger_id": f"trigger-{index}",
                "user": {"id": "UOWNER"},
                "channel": {"id": "C1"},
                "message": {"ts": "555.1", "thread_ts": "500.1"},
                "actions": [{"action_id": action_id, "value": json.dumps({"item_type": "concept", "item_id": "concept-a"})}],
            }
        )

    assert [item["action"] for item in receiver.approvals] == ["approve", "pass", "more_like_this"]
    assert all(item["source_thread_id"] == "500.1" for item in receiver.approvals)


def test_slack_status_updates_and_https_images_stay_in_one_thread(repository: RepositoryService) -> None:
    _service, tasks, _receiver, transport = configured_slack(repository)
    channel = SlackAgentChannel(transport, tasks, default_channel="C1")
    channel.send_status("500.1", "Preparing", channel_id="C1")
    channel.send_status("500.1", "Generating", channel_id="C1", message_id="status.1")
    channel.send_image("500.1", "https://cdn.example/dinkly.png", "COFFEE / COFFEE WITH YOU", channel_id="C1", details="QA passed")

    assert any(method == "chat.update" and payload["ts"] == "status.1" for method, payload in transport.calls)
    image = next(payload for method, payload in transport.calls if method == "chat.postMessage" and payload.get("blocks"))
    assert image["thread_ts"] == "500.1"
    assert image["blocks"][1]["image_url"] == "https://cdn.example/dinkly.png"
    assert public_asset_url("http://127.0.0.1:8000", "/generation-assets/local.png") is None

    channel.send_buttons(
        "500.1",
        "Ready for you",
        [{"label": "Open in DINKLY", "action_id": "dinkly_open_comic", "value": "comic-1", "url": "https://dinkly.example/approvals"}],
        channel_id="C1",
    )
    buttons = [payload for method, payload in transport.calls if method == "chat.postMessage" and payload.get("blocks")][-1]
    assert buttons["blocks"][1]["elements"][0]["url"] == "https://dinkly.example/approvals"


def test_slack_status_button_update_preserves_exact_live_task_link(repository: RepositoryService) -> None:
    _service, tasks, _receiver, transport = configured_slack(repository)
    channel = SlackAgentChannel(transport, tasks, default_channel="C1")
    channel.update_buttons(
        "status.1",
        "DINKLY Agent · Working",
        [{"label": "See task running", "action_id": "dinkly_open_task", "value": "task-1", "url": "http://127.0.0.1:3000/agent/tasks/task-1"}],
        channel_id="C1",
    )

    update = next(payload for method, payload in transport.calls if method == "chat.update")
    assert update["ts"] == "status.1"
    assert update["blocks"][1]["elements"][0]["url"].endswith("/agent/tasks/task-1")
