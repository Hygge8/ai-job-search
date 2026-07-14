"""Authenticated API routes for browser-managed server settings."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from webapp.main import require_auth
from webapp.settings_service import service


router = APIRouter(prefix="/api/settings", tags=["settings"])


class SettingsUpdate(BaseModel):
    openai_base_url: Optional[str] = Field(default=None, max_length=2000)
    openai_model_name: Optional[str] = Field(default=None, max_length=300)
    openai_vision_model_name: Optional[str] = Field(default=None, max_length=300)
    openai_api_key: Optional[str] = Field(default=None, max_length=1000)
    clear_openai_api_key: bool = False

    ai_timeout_seconds: Optional[float] = Field(default=None, ge=10, le=600)
    strict_apply_mode: Optional[bool] = None
    apply_max_repair_attempts: Optional[int] = Field(default=None, ge=1, le=10)

    tavily_api_key: Optional[str] = Field(default=None, max_length=1000)
    clear_tavily_api_key: bool = False
    require_company_research: Optional[bool] = None

    web_username: Optional[str] = Field(default=None, min_length=3, max_length=100)
    web_password: Optional[str] = Field(default=None, max_length=300)


@router.get("")
async def read_settings(_: str = Depends(require_auth)):
    return service.public()


@router.put("")
async def update_settings(payload: SettingsUpdate, _: str = Depends(require_auth)):
    try:
        return service.save(payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/test-text")
async def test_text_model(_: str = Depends(require_auth)):
    try:
        return service.test_text_model()
    except RuntimeError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/test-vision")
async def test_vision_model(_: str = Depends(require_auth)):
    try:
        return service.test_vision_model()
    except RuntimeError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/test-tavily")
async def test_tavily(_: str = Depends(require_auth)):
    try:
        return service.test_tavily()
    except RuntimeError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
