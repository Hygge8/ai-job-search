"""Source-level smoke tests for the optional web application.

These tests intentionally use only the standard library so the repository's existing
Python test job can validate the web scaffold without installing web dependencies.
"""

import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class WebAppSourceTests(unittest.TestCase):
    def test_backend_is_valid_python(self):
        source = (ROOT / "webapp" / "main.py").read_text(encoding="utf-8")
        ast.parse(source)

    def test_frontend_contains_required_workflows(self):
        html = (ROOT / "webapp" / "index.html").read_text(encoding="utf-8")
        for marker in (
            "候选人档案",
            "岗位搜索",
            "分析与申请",
            "/api/jobs/search",
            "/api/jobs/evaluate",
            "/api/applications/generate",
        ):
            self.assertIn(marker, html)

    def test_environment_template_does_not_contain_real_key(self):
        env_text = (ROOT / ".env.web.example").read_text(encoding="utf-8")
        self.assertIn("OPENAI_API_KEY=sk-...", env_text)
        self.assertNotIn("WEB_PASSWORD=admin123", env_text)

    def test_runtime_secrets_are_ignored(self):
        gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
        self.assertIn(".env.web", gitignore)
        self.assertIn("web-data/", gitignore)


if __name__ == "__main__":
    unittest.main()
