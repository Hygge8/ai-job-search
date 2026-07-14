"""Source-level checks for the complete browser /apply workflow.

The default CI job does not install the optional web runtime, so these tests
validate syntax, route wiring, ordered stages, and privacy rules without
importing FastAPI or OpenAI.
"""
from __future__ import annotations

import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class FullApplySourceTests(unittest.TestCase):
    def test_backend_sources_parse(self):
        for relative in (
            "webapp/apply_common.py",
            "webapp/apply_documents.py",
            "webapp/apply_pdf.py",
            "webapp/full_apply.py",
            "webapp/full_app.py",
        ):
            source = (ROOT / relative).read_text(encoding="utf-8")
            ast.parse(source, filename=relative)

    def test_ordered_workflow_markers_are_present(self):
        source = (ROOT / "webapp/full_apply.py").read_text(encoding="utf-8")
        for marker in (
            '("parse","解析岗位信息")',
            '("evaluate","匹配度评估")',
            '("confirm","等待用户确认")',
            '("draft","生成 CV 与求职信初稿")',
            '("review","独立 Reviewer 复审")',
            '("compile","LaTeX 编译与修复")',
            '("visual","PDF 渲染与视觉检查")',
            '("ats","ATS 文本层与关键词检查")',
            '("verify","最终核验与报告")',
        ):
            self.assertIn(marker, source)
        pdf_source = (ROOT / "webapp/apply_pdf.py").read_text(encoding="utf-8")
        for marker in ("lualatex", "xelatex", "pdftoppm", "pdftotext", "pdfinfo"):
            self.assertIn(marker, pdf_source)

    def test_routes_and_ui_are_wired(self):
        routes = (ROOT / "webapp/full_app.py").read_text(encoding="utf-8")
        ui = (ROOT / "webapp/index.html").read_text(encoding="utf-8")
        for marker in (
            "/api/full-apply/evaluate",
            "/api/full-apply/{job_id}/confirm",
            "/api/full-apply/{job_id}/download/{name:path}",
        ):
            self.assertIn(marker, routes)
        self.assertIn("完整 /apply", ui)
        self.assertIn("/api/full-apply/evaluate", ui)
        self.assertIn("/api/full-apply/${state.applyId}/confirm", ui)

    def test_secrets_and_artifacts_are_ignored(self):
        rules = (ROOT / ".gitignore").read_text(encoding="utf-8")
        self.assertIn(".env.web", rules)
        self.assertIn("web-data/", rules)
        dockerignore = (ROOT / ".dockerignore").read_text(encoding="utf-8")
        for marker in (".env.*", "documents/", "web-data/", "01-candidate-profile.md"):
            self.assertIn(marker, dockerignore)


if __name__ == "__main__":
    unittest.main()
