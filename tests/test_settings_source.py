"""Source-level checks for browser-managed server settings."""
from __future__ import annotations

import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class SettingsSourceTests(unittest.TestCase):
    def test_settings_backend_sources_parse(self):
        for relative in ("webapp/settings_service.py", "webapp/settings_api.py"):
            source = (ROOT / relative).read_text(encoding="utf-8")
            ast.parse(source, filename=relative)

    def test_settings_routes_are_registered(self):
        api = (ROOT / "webapp/settings_api.py").read_text(encoding="utf-8")
        app = (ROOT / "webapp/full_app.py").read_text(encoding="utf-8")
        for marker in (
            'prefix="/api/settings"',
            '@router.get("")',
            '@router.put("")',
            '@router.post("/test-text")',
            '@router.post("/test-vision")',
            '@router.post("/test-tavily")',
        ):
            self.assertIn(marker, api)
        self.assertIn("app.include_router(settings_router)", app)

    def test_secrets_are_not_returned_by_public_settings(self):
        service = (ROOT / "webapp/settings_service.py").read_text(encoding="utf-8")
        public_block = service.split("def public", 1)[1].split("def save", 1)[0]
        self.assertIn("openai_api_key_configured", public_block)
        self.assertIn("tavily_api_key_configured", public_block)
        self.assertNotIn('"openai_api_key":', public_block)
        self.assertNotIn('"tavily_api_key":', public_block)
        self.assertNotIn('"web_password":', public_block)

    def test_runtime_settings_are_applied_to_all_workflow_modules(self):
        service = (ROOT / "webapp/settings_service.py").read_text(encoding="utf-8")
        for marker in (
            "main.OPENAI_API_KEY",
            "apply_common.OPENAI_VISION_MODEL_NAME",
            "apply_documents.TAVILY_API_KEY",
            "apply_pdf.MAX_REPAIRS",
            "full_apply.STRICT",
        ):
            self.assertIn(marker, service)

    def test_frontend_has_settings_and_connection_tests(self):
        html = (ROOT / "webapp/index.html").read_text(encoding="utf-8")
        for marker in (
            "系统设置",
            "/api/settings",
            "/api/settings/test-text",
            "/api/settings/test-vision",
            "/api/settings/test-tavily",
            "密钥保存在服务端 SQLite",
        ):
            self.assertIn(marker, html)


if __name__ == "__main__":
    unittest.main()
