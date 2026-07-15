"""LaTeX generation artifacts, compile/repair loop, visual inspection and ATS checks."""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from webapp.apply_common import ApplyContext, FILES, MAX_REPAIRS, STRICT


@dataclass
class CompileResult:
    ok: bool
    command: list[str]
    stdout: str
    log: str
    pdf: Path
    pages: int | None


class PdfWorkflow:
    def __init__(self, ctx: ApplyContext): self.ctx=ctx

    def prepare(self, root: Path, job, cv, cover):
        company=self.ctx.slug(job.get("company") or "company"); role=self.ctx.slug(job.get("title") or "role")
        cv_dir=root/"cv"; cover_dir=root/"cover_letters"; cv_dir.mkdir(parents=True,exist_ok=True); cover_dir.mkdir(parents=True,exist_ok=True)
        cv_path=cv_dir/f"main_{company}.tex"; cover_path=cover_dir/f"cover_{company}_{role}.tex"
        cv_path.write_text(cv,encoding="utf-8"); cover_path.write_text(cover,encoding="utf-8")
        if FILES["cover_class"].exists(): shutil.copy2(FILES["cover_class"],cover_dir/"cover.cls")
        if FILES["cover_fonts"].exists():
            dst=cover_dir/"OpenFonts"; shutil.rmtree(dst,ignore_errors=True); shutil.copytree(FILES["cover_fonts"],dst)
        return cv_dir,cover_dir,cv_path,cover_path

    def compile_visual_loop(self,job,evaluation,cv_path,cover_path,cv,cover):
        attempts=[]; visual={}
        for attempt in range(1,MAX_REPAIRS+1):
            cr=self.compile("lualatex",cv_path); lr=self.compile("xelatex",cover_path)
            entry={"attempt":attempt,"cv":self.compile_dict(cr),"cover":self.compile_dict(lr)}; attempts.append(entry)
            if not cr.ok or not lr.ok:
                if attempt==MAX_REPAIRS: raise RuntimeError("LaTeX 编译在最大修复次数后仍失败")
                cv,cover=self.repair(job,evaluation,cv,cover,cr,lr,[]); cv_path.write_text(cv,encoding="utf-8"); cover_path.write_text(cover,encoding="utf-8"); continue
            cv_imgs=self.render(cr.pdf,cv_path.parent/"render_cv"); cover_imgs=self.render(lr.pdf,cover_path.parent/"render_cover")
            mechanical=[]
            if cr.pages!=2: mechanical.append(f"CV 页数为 {cr.pages}，必须为 2")
            if lr.pages!=1: mechanical.append(f"求职信页数为 {lr.pages}，必须为 1")
            try: visual=self.visual_review(cv_imgs,cover_imgs,mechanical)
            except Exception as exc:
                if STRICT: raise RuntimeError(f"视觉模型检查失败：{exc}") from exc
                visual={"pass":not mechanical,"degraded":True,"issues":mechanical+[str(exc)]}
            entry["visual"]=visual
            if visual.get("pass") and not mechanical: return {"passed":True,"attempts":attempts},visual,cv,cover
            if attempt==MAX_REPAIRS: raise RuntimeError("PDF 布局在最大修复次数后仍未通过")
            issues=mechanical+list(visual.get("issues") or [])+list(visual.get("cv_issues") or [])+list(visual.get("cover_issues") or [])
            cv,cover=self.repair(job,evaluation,cv,cover,cr,lr,issues); cv_path.write_text(cv,encoding="utf-8"); cover_path.write_text(cover,encoding="utf-8")
        raise RuntimeError("PDF 编译检查未完成")

    def compile(self,engine,tex):
        cmd=[engine,"-interaction=nonstopmode","-halt-on-error",tex.name]
        try:
            r=subprocess.run(cmd,cwd=tex.parent,capture_output=True,text=True,encoding="utf-8",errors="replace",timeout=180)
            stdout=r.stdout+"\n"+r.stderr
        except Exception as exc: return CompileResult(False,cmd,"",str(exc),tex.with_suffix(".pdf"),None)
        log=self.ctx.read(tex.with_suffix(".log"),200000); pdf=tex.with_suffix(".pdf"); ok=r.returncode==0 and pdf.exists()
        return CompileResult(ok,cmd,stdout[-8000:],(log or stdout)[-12000:],pdf,self.pages(pdf) if ok else None)
    def pages(self,pdf):
        r=subprocess.run(["pdfinfo",str(pdf)],capture_output=True,text=True,encoding="utf-8",errors="replace")
        m=re.search(r"^Pages:\s+(\d+)",r.stdout,re.M); return int(m.group(1)) if m else None
    def render(self,pdf,prefix):
        for p in prefix.parent.glob(prefix.name+"-*.png"): p.unlink(missing_ok=True)
        r=subprocess.run(["pdftoppm","-png","-r","144",str(pdf),str(prefix)],capture_output=True,text=True,encoding="utf-8",errors="replace",timeout=120)
        if r.returncode: raise RuntimeError("PDF 渲染失败："+r.stderr[-2000:])
        images=sorted(prefix.parent.glob(prefix.name+"-*.png"))
        if not images: raise RuntimeError("PDF 渲染没有生成图片")
        return images
    def visual_review(self,cv_images,cover_images,mechanical):
        prompt=f"""First {len(cv_images)} images are CV pages, final {len(cover_images)} are cover letter. Mechanical issues: {json.dumps(mechanical,ensure_ascii=False)}.
Verify: CV exactly 2 pages; cover exactly 1; no clipping/overlap/broken glyphs/black boxes; no CV cventry title orphaned at page 1 bottom; no isolated heading; no awkward whitespace; signature visible; cover bullet font matches body; consistent alignment.
Return JSON {{"pass":true,"issues":[""],"cv_issues":[""],"cover_issues":[""],"repair_instructions":[""]}}."""
        return self.ctx.vision(prompt,cv_images+cover_images)
    def repair(self,job,evaluation,cv,cover,cr,lr,issues):
        prompt=f"""Repair both complete LaTeX files for Step 5. Never add facts. Use relevance-weighted cutting, not smaller geometry/spacing. CV lualatex exactly 2 pages; cover xelatex exactly 1. Use needspace and correct cover itemize/font pattern.
Job/evaluation: {json.dumps(job,ensure_ascii=False)} {json.dumps(evaluation,ensure_ascii=False)}
Issues: {json.dumps(issues,ensure_ascii=False)}
CV compile: {json.dumps(self.compile_dict(cr),ensure_ascii=False)}
Cover compile: {json.dumps(self.compile_dict(lr),ensure_ascii=False)}
CV: {cv}
Cover: {cover}
Return only <CV_TEX>complete corrected CV</CV_TEX><COVER_TEX>complete corrected cover</COVER_TEX>."""
        text=self.ctx.chat("LaTeX repair specialist. Tagged complete files only.",prompt); new_cv=self.ctx.tag(text,"CV_TEX"); new_cover=self.ctx.tag(text,"COVER_TEX"); self.ctx.validate_tex(new_cv,new_cover); return new_cv,new_cover
    def compile_dict(self,r): return {"ok":r.ok,"command":r.command,"pages":r.pages,"stdout_tail":r.stdout,"log_tail":r.log,"pdf":r.pdf.name}

    def ats(self,job,evaluation,pdf,cv):
        txt=pdf.with_suffix(".txt")
        r=subprocess.run(["pdftotext","-layout",str(pdf),str(txt)],capture_output=True,text=True,encoding="utf-8",errors="replace",timeout=60)
        if r.returncode or not txt.exists():
            if STRICT: raise RuntimeError("pdftotext 失败："+r.stderr[-2000:])
            extracted=""
        else: extracted=txt.read_text(encoding="utf-8",errors="replace")
        txt.unlink(missing_ok=True); profile=self.ctx.profile()
        emails=sorted(set(re.findall(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",profile)))
        phones=sorted(set(re.findall(r"(?<!\d)(?:\+?\d[\d ()-]{7,}\d)(?!\d)",profile)))[:5]
        parseability={"text_extracted":bool(extracted.strip()),"cid_markers":"(cid:" in extracted,"replacement_characters":"�" in extracted,"emails_expected":emails,"emails_present":[x for x in emails if x in extracted],"phones_expected":phones,"phones_present":[x for x in phones if self.digits(x) in self.digits(extracted)],"section_order":self.section_order(extracted)}
        prompt=f"""Perform Step 5d keyword coverage. Never keyword-stuff unsupported skills.
Job/evaluation: {json.dumps(job,ensure_ascii=False)} {json.dumps(evaluation,ensure_ascii=False)}
Profile: {profile}
Extracted CV text: {extracted[:60000]}
Return JSON {{"coverage":[{{"keyword":"","priority":"required|preferred","status":"covered|synonym-only|missing (have it)|missing (gap)","note":""}}],"missing_have_it":[""],"missing_gaps":[""],"reading_order_ok":true,"dates_recognizable":true,"notes":[""]}}."""
        coverage=self.ctx.json("ATS text-layer and keyword auditor. JSON only.",prompt); report={"parseability":parseability,**coverage,"cv_tex_length":len(cv)}
        report["missing_have_it"]=[x for x in coverage.get("missing_have_it",[]) if x]
        failures=[]
        if not parseability["text_extracted"]: failures.append("PDF 文本层为空")
        if parseability["cid_markers"] or parseability["replacement_characters"]: failures.append("PDF 文本层存在乱码")
        if emails and len(parseability["emails_present"])!=len(emails): failures.append("邮箱未全部以字面文本保留")
        if phones and not parseability["phones_present"]: failures.append("电话号码未以字面文本保留")
        if failures and STRICT: raise RuntimeError("ATS 解析检查失败："+"；".join(failures))
        report["mechanical_failures"]=failures; return report
    def repair_ats(self,job,evaluation,cv,report):
        prompt=f"""Revise complete CV LaTeX only for keywords classified missing (have it). Use only profile evidence; prefer experience bullets; do not add gaps; preserve exactly 2 pages.
Job/evaluation: {json.dumps(job,ensure_ascii=False)} {json.dumps(evaluation,ensure_ascii=False)}
ATS report: {json.dumps(report,ensure_ascii=False)}
Profile: {self.ctx.profile()}
CV: {cv}
Return only <CV_TEX>complete corrected CV</CV_TEX>."""
        out=self.ctx.tag(self.ctx.chat("ATS wording improver without fabrication.",prompt),"CV_TEX")
        if "\\documentclass" not in out or "\\end{document}" not in out: raise RuntimeError("ATS 修订未返回完整 CV")
        return out

    def cleanup(self,directory):
        for suffix in (".aux",".log",".out",".toc",".fls",".fdb_latexmk",".synctex.gz"):
            for p in directory.glob("*"+suffix): p.unlink(missing_ok=True)
        for p in directory.glob("render_*-*.png"): p.unlink(missing_ok=True)
    def digits(self,value): return "".join(re.findall(r"\d",value))
    def section_order(self,text):
        names=["Profile","Core Competencies","Professional Experience","Education","Languages","Publications","Honors","References"]
        return [name for pos,name in sorted((text.lower().find(name.lower()),name) for name in names) if pos>=0]
