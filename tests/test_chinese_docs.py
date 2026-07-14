"""Source-level checks for the Simplified Chinese documentation."""

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ChineseDocumentationTests(unittest.TestCase):
    def test_required_chinese_documents_exist(self):
        for relative in ("README.zh-CN.md", "WEB_APP.zh-CN.md", "中文文档.md"):
            path = ROOT / relative
            self.assertTrue(path.is_file(), relative)
            self.assertGreater(len(path.read_text(encoding="utf-8")), 200, relative)

    def test_main_chinese_readme_covers_core_workflows(self):
        text = (ROOT / "README.zh-CN.md").read_text(encoding="utf-8")
        for marker in (
            "/setup",
            "/scrape",
            "/apply",
            "系统设置",
            "Docker Compose",
            "STRICT_APPLY_MODE",
            "web-data/app.sqlite3",
            "国内招聘网站",
        ):
            self.assertIn(marker, text)

    def test_web_guide_covers_deployment_and_security(self):
        text = (ROOT / "WEB_APP.zh-CN.md").read_text(encoding="utf-8")
        for marker in (
            "docker compose",
            "测试文本模型",
            "测试视觉模型",
            "测试 Tavily",
            "ATS",
            "数据安全",
            "application_bundle.zip",
        ):
            self.assertIn(marker, text)


if __name__ == "__main__":
    unittest.main()
