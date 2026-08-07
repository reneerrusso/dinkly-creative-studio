from __future__ import annotations

import json
import logging
from urllib.parse import parse_qs

from fastapi import APIRouter, Request, status

from app.backend.models.dinkly_agent import SlackConnectRequest, SlackSettingsUpdate
from app.backend.routers.dinkly_agent import agent, repository, task_service
from app.backend.services.repository_service import RepositoryError
from app.backend.services.slack_service import SlackService

router = APIRouter(prefix="/api/slack", tags=["slack"])
service = SlackService(
    repository,
    task_service,
    agent.receive_instruction,
    agent.receive_approval,
    cancellation_receiver=agent.request_cancellation,
)
logger = logging.getLogger(__name__)


@router.get("/status")
def slack_status() -> dict:
    return service.status()


@router.post("/connect")
def connect(payload: SlackConnectRequest) -> dict:
    logger.info("Slack request path=/api/slack/connect mode=%s", payload.mode)
    return service.connect(payload)


@router.put("/settings")
def update_settings(payload: SlackSettingsUpdate) -> dict:
    logger.info("Slack request path=/api/slack/settings mode=%s", payload.mode)
    return service.update_settings(payload)


@router.post("/test")
def test_connection() -> dict:
    logger.info("Slack request path=/api/slack/test mode=%s", service.settings()["mode"])
    return service.test_connection()


@router.get("/diagnostics")
def diagnostics() -> dict:
    logger.info("Slack request path=/api/slack/diagnostics mode=%s", service.settings()["mode"])
    return service.diagnostics()


@router.post("/test/end-to-end")
def end_to_end_test() -> dict:
    logger.info("Slack request path=/api/slack/test/end-to-end mode=%s", service.settings()["mode"])
    return service.run_end_to_end_test()


@router.delete("/disconnect")
def disconnect() -> dict:
    return service.disconnect()


@router.post("/events", status_code=status.HTTP_200_OK)
async def events(request: Request) -> dict:
    body = await request.body()
    headers = {key.lower(): value for key, value in request.headers.items()}
    if not service.verify_request(headers, body):
        raise RepositoryError("Invalid Slack request signature")
    payload = json.loads(body.decode("utf-8"))
    if payload.get("type") == "url_verification":
        return {"challenge": payload.get("challenge")}
    return service.receive_event(payload)


@router.post("/interactions", status_code=status.HTTP_200_OK)
async def interactions(request: Request) -> dict:
    body = await request.body()
    headers = {key.lower(): value for key, value in request.headers.items()}
    if not service.verify_request(headers, body):
        raise RepositoryError("Invalid Slack request signature")
    values = parse_qs(body.decode("utf-8"), keep_blank_values=True)
    if not values.get("payload"):
        raise RepositoryError("Slack interaction payload is missing")
    return service.receive_interaction(json.loads(values["payload"][0]))
