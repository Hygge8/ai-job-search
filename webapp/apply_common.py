"""Shared configuration, model access, persistence, and safe fetch helpers."""
from __future__ import annotations

import base64
import ipaddress
import json
import os
import re
import shutil
import socket
import sqlite3
import subprocess
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse

import httpx
from openai import OpenAI
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[1]
DATABASE_FILE = Path(os.getenv("WEB_DATABASE_FILE", str(ROOT / "web-data/app.sqlite3")))
ARTIFACT_ROOT = Path(os.getenv("APPLY_ARTIFACT_ROOT", str(ROOT / "web-data/applications")))
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "").strip()
OPENAI_MODEL_NAME = os.getenv("OPENAI_MODEL_NAME", "").strip()
OPENAI_VISION_MODEL_NAME = os.getenv("OPENAI_VISION_MODEL_NAME", OPENAI_MODEL_NAME).strip()
AI_TIMEOUT_SECONDS = float(os.getenv("AI_TIMEOUT_SECONDS", "180"))
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "").strip()
MAX_REPAIRS = int(os.getenv("APPLY_MAX_REPAIR_ATTEMPTS", "3"))
STRICT = os.getenv("STRICT_APPLY_MODE", "true").lower() in {"1", "true", "yes", "on"}
REQUIRE_RESEARCH = os.getenv("REQUIRE_COMPANY_RESEARCH", "false").lower() in {"1", "true", "yes", "on"}

SKILL = ROOT / ".claude/skills/job-application-assistant"
FILES = {
    "profile": SKILL / "01-candidate-profile.md",
    "behavior": SKILL / "02-behavioral-profile.md",
    "writing": SKILL / "03-writing-style.md",
    "evaluation": SKILL / "04-job-evaluation.md",
    "cv_guide": SKILL / "05-cv-templates.md",
    "cover_guide": SKILL / "06-cover-letter-templates.md",
    "interview": SKILL / "07-interview-prep.md",
    "claude": ROOT / "CLAUDE.md",
    "cv_example": ROOT / "cv/main_example.tex",
    "cover_example": ROOT / "cover_letters/cover_example.tex",
    "cover_class": ROOT / "cover_letters/cover.cls",
    "cover_fonts": ROOT / "cover_letters/OpenFonts",
    "salary_tool": ROOT / "salary_lookup.py",
}


class FullApplyRequest(BaseModel):
    title: str = Field(default="", max_length=300)
    company: str = Field(default="", max_length=300)
    department: str = Field(default="", max_length=300)
    location: str = Field(default="", max_length=300)
    url: str = Field(default="", max_length=2000)
    description: str = Field(default="", max_length=150000)
    language: str = Field(default="auto", max_length=50)


class TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "noscript", "svg"}:
            self.skip += 1
        elif tag in {"p", "div", "br", "li", "h1", "h2", "h3", "tr"}:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in {"script", "style", "noscript", "svg"} and self.skip:
            self.skip -= 1
        elif tag in {"p", "div", "li", "h1", "h2", "h3", "tr"}:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)

    def text(self):
        value = " ".join(self.parts)
        value = re.sub(r"[ \t\r\f\v]+", " ", value)
        return re.sub(r"\n\s*\n+", "\n\n", value).strip()


class ApplyContext:
    def __init__(self):
        DATABASE_FILE.parent.mkdir(parents=True, exist_ok=True)
        ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)

    def connection(self):
        con = sqlite3.connect(DATABASE_FILE, timeout=30)
        con.row_factory = sqlite3.Row
        return con

    def now(self):
        return datetime.now(timezone.utc).isoformat(timespec="seconds")

    def read(self, path: Path, limit=80000):
        return path.read_text(encoding="utf-8", errors="replace")[:limit] if path.is_file() else ""

    def profile(self):
        try:
            with self.connection() as con:
                row = con.execute("SELECT content FROM profile WHERE id=1").fetchone()
            if row and row["content"]:
                return str(row["content"])
        except sqlite3.OperationalError:
            pass
        return self.read(FILES["profile"])

    def refs(self):
        return {name: self.read(path) for name, path in FILES.items() if name not in {"cover_fonts"}}

    def client(self):
        if not OPENAI_API_KEY or not OPENAI_MODEL_NAME:
            raise RuntimeError("请配置 OPENAI_API_KEY 和 OPENAI_MODEL_NAME")
        args = {"api_key": OPENAI_API_KEY, "timeout": AI_TIMEOUT_SECONDS}
        if OPENAI_BASE_URL:
            args["base_url"] = OPENAI_BASE_URL
        return OpenAI(**args)

    def chat(self, system, user, model=None):
        response = self.client().chat.completions.create(
            model=model or OPENAI_MODEL_NAME,
            temperature=0.2,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        )
        return response.choices[0].message.content or ""

    def json(self, system, user, model=None):
        return self.parse_json(self.chat(system, user, model))

    def vision(self, prompt, images):
        if not OPENAI_VISION_MODEL_NAME:
            raise RuntimeError("请配置 OPENAI_VISION_MODEL_NAME")
        content = [{"type": "text", "text": prompt}]
        for path in images:
            data = base64.b64encode(path.read_bytes()).decode()
            content.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{data}"}})
        response = self.client().chat.completions.create(
            model=OPENAI_VISION_MODEL_NAME,
            temperature=0,
            messages=[
                {"role": "system", "content": "Meticulous PDF layout reviewer. JSON only."},
                {"role": "user", "content": content},
            ],
        )
        return self.parse_json(response.choices[0].message.content or "")

    def parse_json(self, text):
        value = text.strip()
        if value.startswith("```"):
            lines = value.splitlines()[1:]
            lines = lines[:-1] if lines and lines[-1].strip().startswith("```") else lines
            value = "\n".join(lines).strip()
        try:
            out = json.loads(value)
            if isinstance(out, dict):
                return out
        except json.JSONDecodeError:
            pass
        start, end = value.find("{"), value.rfind("}")
        if start >= 0 and end > start:
            try:
                out = json.loads(value[start : end + 1])
                if isinstance(out, dict):
                    return out
            except json.JSONDecodeError:
                pass
        raise RuntimeError("模型未返回有效 JSON：" + value[:500])

    def tag(self, text, name):
        match = re.search(rf"<{name}>\s*(.*?)\s*</{name}>", text, re.S | re.I)
        if not match:
            raise RuntimeError(f"模型输出缺少 <{name}>")
        return match.group(1).strip()

    def validate_url(self, url):
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise RuntimeError("只允许公开 http/https URL")
        host = parsed.hostname.lower().strip(".")
        if host in {"localhost", "localhost.localdomain"} or host.endswith(".local"):
            raise RuntimeError("禁止访问本机或内网")
        try:
            infos = socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80))
        except socket.gaierror as exc:
            raise RuntimeError(f"域名无法解析：{exc}") from exc
        if any(not ipaddress.ip_address(info[4][0]).is_global for info in infos):
            raise RuntimeError("禁止访问非公网 IP")

    def fetch(self, url, max_bytes=2_000_000):
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; AIJobSearchPersonal/1.0)",
            "Accept": "text/html,text/plain;q=.9,*/*;q=.5",
        }
        current = url
        with httpx.Client(timeout=25, follow_redirects=False, headers=headers) as client:
            for _ in range(6):
                self.validate_url(current)
                response = client.get(current)
                if response.status_code in {301, 302, 303, 307, 308}:
                    location = response.headers.get("location")
                    if not location:
                        raise RuntimeError("重定向缺少 Location")
                    current = urljoin(current, location)
                    continue
                response.raise_for_status()
                raw = response.content[:max_bytes]
                content_type = response.headers.get("content-type", "")
                encoding = response.encoding or "utf-8"
                break
            else:
                raise RuntimeError("岗位页面重定向次数过多")
        text = raw.decode(encoding, errors="replace")
        if "html" in content_type.lower() or "<html" in text[:500].lower():
            parser = TextExtractor()
            parser.feed(text)
            text = parser.text()
        return text[:120000]

    def salary(self, company, location):
        data = ROOT / "salary_data.json"
        tool = FILES["salary_tool"]
        if not company or not data.exists() or not tool.exists():
            return {"available": False, "reason": "salary_data.json 未配置"}
        cmd = [shutil.which("python") or "python", str(tool), company, "--json"]
        city = location.split(",")[0].strip()
        if city:
            cmd += ["--city", city]
        try:
            result = subprocess.run(
                cmd,
                cwd=ROOT,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=30,
            )
        except Exception as exc:
            return {"available": False, "reason": str(exc)}
        if result.returncode:
            return {"available": False, "reason": (result.stderr or result.stdout)[-1000:]}
        try:
            return {"available": True, "data": json.loads(result.stdout)}
        except json.JSONDecodeError:
            return {"available": False, "reason": "薪资工具返回无效 JSON"}

    def slug(self, value):
        text = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "-", str(value or "").lower()).strip("-")
        return (text or "item")[:80]

    def write_json(self, path, value):
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")

    def validate_tex(self, cv, cover):
        for label, text in (("CV", cv), ("求职信", cover)):
            if "\\documentclass" not in text or "\\begin{document}" not in text or "\\end{document}" not in text:
                raise RuntimeError(f"{label} 不是完整 LaTeX")
            if len(text) > 120000:
                raise RuntimeError(f"{label} 内容异常过长")

    def preflight(self):
        missing = []
        if not OPENAI_API_KEY or not OPENAI_MODEL_NAME:
            missing.append("OPENAI_API_KEY/OPENAI_MODEL_NAME")
        for command in ("lualatex", "xelatex", "pdfinfo", "pdftoppm", "pdftotext"):
            if not shutil.which(command):
                missing.append(command)
        if STRICT and not OPENAI_VISION_MODEL_NAME:
            missing.append("OPENAI_VISION_MODEL_NAME")
        if REQUIRE_RESEARCH and not TAVILY_API_KEY:
            missing.append("TAVILY_API_KEY")
        if missing:
            raise RuntimeError("完整 /apply 前置条件缺失：" + ", ".join(missing))
