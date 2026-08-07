"""Deprecated API import retained for integrations using the former module."""

from app.backend.routers.concept_generator import compatibility_router as router
from app.backend.routers.concept_generator import service

__all__ = ["router", "service"]
