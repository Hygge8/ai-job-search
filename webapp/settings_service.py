"""Persistent server-side settings for the browser application.

Secrets are stored in the local SQLite database and are never returned to the
browser. Environment variables remain bootstrap defaults; saved browser values
override them at runtime and survive container restarts through web-data/.
"""
from __future__ import annotations

import os
import sqlite3
import time
from pathlib import Path
from typing import Any

import httpx
from openai import OpenAI


ROOT = Path(__file__).resolve().parents[1]
DATABASE_FILE = Path(os.getenv("WEB_DATABASE_FILE", str(ROOT / "web-data/app.sqlite3")))

DEFAULTS: dict[str, str] = {
    "OPENAI_API_KEY": "",
    "OPENAI_BASE_URL": "",
    "OPENAI_MODEL_NAME": "",
    "OPENAI_VISION_MODEL_NAME": "",
    "AI_TIMEOUT_SECONDS": "180",
    "TAVILY_API_KEY": "",
    "STRICT_APPLY_MODE": "true",
    "APPLY_MAX_REPAIR_ATTEMPTS": "3",
    "REQUIRE_COMPANY_RESEARCH": "false",
    "WEB_USERNAME": "admin",
    "WEB_PASSWORD": "admin123",
}


def _as_bool(value: str) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _safe_error(exc: Exception, secrets: list[str]) -> str:
    message = str(exc)
    for secret in secrets:
        if secret:
            message = message.replace(secret, "***")
    return message[:1500]


class SettingsService:
    def __init__(self) -> None:
        DATABASE_FILE.parent.mkdir(parents=True, exist_ok=True)
        self.init_database()
        self.apply_runtime()

    def connection(self) -> sqlite3.Connection:
        connection = sqlite3.connect(DATABASE_FILE, timeout=30)
        connection.row_factory = sqlite3.Row
        return connection

    def init_database(self) -> None:
        with self.connection() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS web_settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        try:
            os.chmod(DATABASE_FILE, 0o600)
        except OSError:
            pass

    def _stored(self) -> dict[str, str]:
        with self.connection() as connection:
            rows = connection.execute("SELECT key, value FROM web_settings").fetchall()
        return {str(row["key"]): str(row["value"]) for row in rows}

    def effective(self) -> dict[str, str]:
        stored = self._stored()
        values: dict[str, str] = {}
        for key, default in DEFAULTS.items():
            values[key] = stored.get(key, os.getenv(key, default))
        return values

    def public(self) -> dict[str, Any]:
        values = self.effective()
        return {
            "openai_base_url": values["OPENAI_BASE_URL"],
            "openai_model_name": values["OPENAI_MODEL_NAME"],
            "openai_vision_model_name": values["OPENAI_VISION_MODEL_NAME"],
            "ai_timeout_seconds": float(values["AI_TIMEOUT_SECONDS"] or 180),
            "strict_apply_mode": _as_bool(values["STRICT_APPLY_MODE"]),
            "apply_max_repair_attempts": int(values["APPLY_MAX_REPAIR_ATTEMPTS"] or 3),
            "require_company_research": _as_bool(values["REQUIRE_COMPANY_RESEARCH"]),
            "web_username": values["WEB_USERNAME"],
            "openai_api_key_configured": bool(values["OPENAI_API_KEY"]),
            "tavily_api_key_configured": bool(values["TAVILY_API_KEY"]),
            "web_password_configured": bool(values["WEB_PASSWORD"]),
            "server_port": int(os.getenv("SERVER_PORT", "8000")),
            "storage": str(DATABASE_FILE),
            "note": "密钥保存在服务端 SQLite 中，页面不会回显明文。端口仍由 Docker/.env.web 管理。",
        }

    def save(self, payload: dict[str, Any]) -> dict[str, Any]:
        updates: dict[str, str] = {}

        text_fields = {
            "openai_base_url": "OPENAI_BASE_URL",
            "openai_model_name": "OPENAI_MODEL_NAME",
            "openai_vision_model_name": "OPENAI_VISION_MODEL_NAME",
            "web_username": "WEB_USERNAME",
        }
        for field, key in text_fields.items():
            value = payload.get(field)
            if value is not None:
                value = str(value).strip()
                if "\n" in value or "\r" in value:
                    raise ValueError(f"{field} 不能包含换行")
                if key == "WEB_USERNAME" and len(value) < 3:
                    raise ValueError("登录用户名至少 3 个字符")
                updates[key] = value

        if payload.get("ai_timeout_seconds") is not None:
            timeout = float(payload["ai_timeout_seconds"])
            if not 10 <= timeout <= 600:
                raise ValueError("AI 超时时间必须在 10 到 600 秒之间")
            updates["AI_TIMEOUT_SECONDS"] = str(timeout)

        if payload.get("apply_max_repair_attempts") is not None:
            repairs = int(payload["apply_max_repair_attempts"])
            if not 1 <= repairs <= 10:
                raise ValueError("自动修复次数必须在 1 到 10 之间")
            updates["APPLY_MAX_REPAIR_ATTEMPTS"] = str(repairs)

        for field, key in (
            ("strict_apply_mode", "STRICT_APPLY_MODE"),
            ("require_company_research", "REQUIRE_COMPANY_RESEARCH"),
        ):
            if payload.get(field) is not None:
                updates[key] = "true" if bool(payload[field]) else "false"

        self._secret_update(
            updates,
            key="OPENAI_API_KEY",
            value=payload.get("openai_api_key"),
            clear=bool(payload.get("clear_openai_api_key")),
            minimum=8,
            label="OpenAI API Key",
        )
        self._secret_update(
            updates,
            key="TAVILY_API_KEY",
            value=payload.get("tavily_api_key"),
            clear=bool(payload.get("clear_tavily_api_key")),
            minimum=8,
            label="Tavily API Key",
        )
        self._secret_update(
            updates,
            key="WEB_PASSWORD",
            value=payload.get("web_password"),
            clear=False,
            minimum=8,
            label="登录密码",
        )

        if updates:
            with self.connection() as connection:
                connection.executemany(
                    """
                    INSERT INTO web_settings(key, value, updated_at)
                    VALUES(?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(key) DO UPDATE SET
                        value = excluded.value,
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    list(updates.items()),
                )
        self.apply_runtime()
        result = self.public()
        result["saved_keys"] = sorted(updates)
        return result

    def _secret_update(
        self,
        updates: dict[str, str],
        *,
        key: str,
        value: Any,
        clear: bool,
        minimum: int,
        label: str,
    ) -> None:
        if clear:
            updates[key] = ""
            return
        if value is None or str(value) == "":
            return
        text = str(value).strip()
        if "\n" in text or "\r" in text:
            raise ValueError(f"{label} 不能包含换行")
        if len(text) < minimum:
            raise ValueError(f"{label} 长度不足")
        updates[key] = text

    def apply_runtime(self) -> None:
        values = self.effective()
        for key, value in values.items():
            os.environ[key] = value

        # Modules intentionally keep simple module-level configuration. Update
        # every imported copy so browser changes take effect without restart.
        from webapp import apply_common, apply_documents, apply_pdf, full_apply, main

        main.OPENAI_API_KEY = values["OPENAI_API_KEY"]
        main.OPENAI_BASE_URL = values["OPENAI_BASE_URL"]
        main.OPENAI_MODEL_NAME = values["OPENAI_MODEL_NAME"]
        main.AI_TIMEOUT_SECONDS = float(values["AI_TIMEOUT_SECONDS"] or 180)
        main.WEB_USERNAME = values["WEB_USERNAME"]
        main.WEB_PASSWORD = values["WEB_PASSWORD"]

        apply_common.OPENAI_API_KEY = values["OPENAI_API_KEY"]
        apply_common.OPENAI_BASE_URL = values["OPENAI_BASE_URL"]
        apply_common.OPENAI_MODEL_NAME = values["OPENAI_MODEL_NAME"]
        apply_common.OPENAI_VISION_MODEL_NAME = (
            values["OPENAI_VISION_MODEL_NAME"] or values["OPENAI_MODEL_NAME"]
        )
        apply_common.AI_TIMEOUT_SECONDS = float(values["AI_TIMEOUT_SECONDS"] or 180)
        apply_common.TAVILY_API_KEY = values["TAVILY_API_KEY"]
        apply_common.MAX_REPAIRS = int(values["APPLY_MAX_REPAIR_ATTEMPTS"] or 3)
        apply_common.STRICT = _as_bool(values["STRICT_APPLY_MODE"])
        apply_common.REQUIRE_RESEARCH = _as_bool(values["REQUIRE_COMPANY_RESEARCH"])

        apply_documents.TAVILY_API_KEY = values["TAVILY_API_KEY"]
        apply_documents.REQUIRE_RESEARCH = _as_bool(values["REQUIRE_COMPANY_RESEARCH"])
        apply_pdf.MAX_REPAIRS = int(values["APPLY_MAX_REPAIR_ATTEMPTS"] or 3)
        apply_pdf.STRICT = _as_bool(values["STRICT_APPLY_MODE"])
        full_apply.STRICT = _as_bool(values["STRICT_APPLY_MODE"])

    def _client(self, model_key: str = "OPENAI_MODEL_NAME") -> tuple[OpenAI, str, dict[str, str]]:
        values = self.effective()
        api_key = values["OPENAI_API_KEY"]
        model = values[model_key] or values["OPENAI_MODEL_NAME"]
        if not api_key or not model:
            raise RuntimeError("请先保存 OpenAI API Key 和模型名称")
        kwargs: dict[str, Any] = {
            "api_key": api_key,
            "timeout": float(values["AI_TIMEOUT_SECONDS"] or 180),
        }
        if values["OPENAI_BASE_URL"]:
            kwargs["base_url"] = values["OPENAI_BASE_URL"]
        return OpenAI(**kwargs), model, values

    def test_text_model(self) -> dict[str, Any]:
        client, model, values = self._client("OPENAI_MODEL_NAME")
        started = time.perf_counter()
        try:
            response = client.chat.completions.create(
                model=model,
                temperature=0,
                messages=[{"role": "user", "content": "Reply with exactly: OK"}],
            )
            reply = (response.choices[0].message.content or "").strip()
        except Exception as exc:
            raise RuntimeError(_safe_error(exc, [values["OPENAI_API_KEY"]])) from exc
        return {
            "ok": True,
            "model": model,
            "reply": reply[:100],
            "latency_ms": round((time.perf_counter() - started) * 1000),
        }

    def test_vision_model(self) -> dict[str, Any]:
        client, model, values = self._client("OPENAI_VISION_MODEL_NAME")
        # Valid 1x1 PNG. The key point is verifying that the provider accepts
        # image_url input for the configured model.
        png = (
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
        )
        started = time.perf_counter()
        try:
            response = client.chat.completions.create(
                model=model,
                temperature=0,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "Confirm you received the image. Reply OK."},
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/png;base64,{png}"},
                            },
                        ],
                    }
                ],
            )
            reply = (response.choices[0].message.content or "").strip()
        except Exception as exc:
            raise RuntimeError(_safe_error(exc, [values["OPENAI_API_KEY"]])) from exc
        return {
            "ok": True,
            "model": model,
            "reply": reply[:100],
            "latency_ms": round((time.perf_counter() - started) * 1000),
        }

    def test_tavily(self) -> dict[str, Any]:
        values = self.effective()
        key = values["TAVILY_API_KEY"]
        if not key:
            raise RuntimeError("请先保存 Tavily API Key")
        started = time.perf_counter()
        try:
            response = httpx.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": key,
                    "query": "OpenAI official website",
                    "search_depth": "basic",
                    "max_results": 1,
                },
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()
        except Exception as exc:
            raise RuntimeError(_safe_error(exc, [key])) from exc
        return {
            "ok": True,
            "results": len(data.get("results", [])),
            "latency_ms": round((time.perf_counter() - started) * 1000),
        }


service = SettingsService()
