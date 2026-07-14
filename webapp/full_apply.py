"""Ordered background manager for the complete browser /apply workflow."""
from __future__ import annotations

import json
import threading
import zipfile
from pathlib import Path

from webapp.apply_common import ApplyContext, ARTIFACT_ROOT, FullApplyRequest, STRICT
from webapp.apply_documents import DocumentWorkflow
from webapp.apply_pdf import PdfWorkflow

STEPS=(
    ("parse","解析岗位信息"),("evaluate","匹配度评估"),("confirm","等待用户确认"),
    ("draft","生成 CV 与求职信初稿"),("research","公司与团队研究"),
    ("review","独立 Reviewer 复审"),("revise","根据复审意见修订"),
    ("compile","LaTeX 编译与修复"),("visual","PDF 渲染与视觉检查"),
    ("ats","ATS 文本层与关键词检查"),("verify","最终核验与报告"),
)


class FullApplyManager:
    def __init__(self):
        self.ctx=ApplyContext(); self.docs=DocumentWorkflow(self.ctx); self.pdf=PdfWorkflow(self.ctx); self.lock=threading.Lock(); self.workers={}; self.init_db()
    def init_db(self):
        with self.ctx.connection() as con:
            con.execute("""CREATE TABLE IF NOT EXISTS full_apply_jobs(id INTEGER PRIMARY KEY AUTOINCREMENT,status TEXT NOT NULL,current_step TEXT,job_json TEXT NOT NULL,evaluation_json TEXT NOT NULL,steps_json TEXT NOT NULL,result_json TEXT NOT NULL,error TEXT,artifact_dir TEXT,created_at TEXT NOT NULL,updated_at TEXT NOT NULL)""")
    def initial_steps(self): return [{"key":k,"label":v,"status":"pending","message":""} for k,v in STEPS]
    def decode(self,value):
        try: return json.loads(value or "{}")
        except json.JSONDecodeError: return {"raw":value}
    def row(self,job_id):
        with self.ctx.connection() as con: row=con.execute("SELECT * FROM full_apply_jobs WHERE id=?",(job_id,)).fetchone()
        if not row: raise KeyError(f"完整 /apply 任务不存在：{job_id}")
        return row
    def update(self,job_id,**fields):
        if not fields:return
        fields["updated_at"]=self.ctx.now(); cols=", ".join(f"{x}=?" for x in fields)
        with self.ctx.connection() as con: con.execute(f"UPDATE full_apply_jobs SET {cols} WHERE id=?",list(fields.values())+[job_id])
    def step(self,job_id,key,status,message=""):
        row=self.row(job_id); steps=self.decode(row["steps_json"])
        for item in steps:
            if item["key"]==key: item.update(status=status,message=message)
            elif status=="running" and item["status"]=="running": item["status"]="completed"
        self.update(job_id,current_step=key,steps_json=json.dumps(steps,ensure_ascii=False),status="running" if status=="running" else row["status"])
    def evaluate(self,payload:FullApplyRequest):
        job,evaluation=self.docs.parse_and_evaluate(payload); steps=self.initial_steps()
        for item in steps:
            if item["key"] in {"parse","evaluate"}: item.update(status="completed",message="已完成")
            elif item["key"]=="confirm": item.update(status="waiting",message="请确认是否继续生成申请材料")
        now=self.ctx.now()
        with self.ctx.connection() as con:
            cur=con.execute("""INSERT INTO full_apply_jobs(status,current_step,job_json,evaluation_json,steps_json,result_json,error,artifact_dir,created_at,updated_at) VALUES(?,?,?,?,?,?,NULL,NULL,?,?)""",("awaiting_confirmation","confirm",json.dumps(job,ensure_ascii=False),json.dumps(evaluation,ensure_ascii=False),json.dumps(steps,ensure_ascii=False),"{}",now,now)); job_id=int(cur.lastrowid)
        return self.get(job_id)
    def confirm(self,job_id):
        row=self.row(job_id)
        if row["status"] not in {"awaiting_confirmation","failed"}: return self.get(job_id)
        self.ctx.preflight(); steps=self.decode(row["steps_json"])
        for item in steps:
            if item["key"]=="confirm": item.update(status="completed",message="用户已确认继续")
            elif item["status"]=="failed": item.update(status="pending",message="")
        self.update(job_id,status="queued",current_step="draft",steps_json=json.dumps(steps,ensure_ascii=False),error=None)
        with self.lock:
            if job_id in self.workers and self.workers[job_id].is_alive(): return self.get(job_id)
            t=threading.Thread(target=self.guarded,args=(job_id,),daemon=True); self.workers[job_id]=t; t.start()
        return self.get(job_id)
    def guarded(self,job_id):
        try:self.run(job_id)
        except Exception as exc:
            row=self.row(job_id); steps=self.decode(row["steps_json"])
            for item in steps:
                if item["key"]==row["current_step"]: item.update(status="failed",message=str(exc))
            self.update(job_id,status="failed",error=str(exc),steps_json=json.dumps(steps,ensure_ascii=False))
        finally:
            with self.lock:self.workers.pop(job_id,None)
    def run(self,job_id):
        row=self.row(job_id); job=self.decode(row["job_json"]); evaluation=self.decode(row["evaluation_json"])
        root=ARTIFACT_ROOT/f"{job_id:06d}_{self.ctx.slug(job.get('company'))}_{self.ctx.slug(job.get('title'))}"; root.mkdir(parents=True,exist_ok=True); self.update(job_id,status="running",artifact_dir=str(root))
        self.ctx.write_json(root/"job.json",job); self.ctx.write_json(root/"evaluation.json",evaluation)
        self.step(job_id,"draft","running","正在生成精确 LaTeX 初稿"); cv,cover,draft=self.docs.draft(job,evaluation); self.ctx.write_json(root/"draft_notes.json",draft); self.step(job_id,"draft","completed","初稿已生成")
        self.step(job_id,"research","running","正在研究公司、团队与近期动态"); research=self.docs.research(job); self.ctx.write_json(root/"company_research.json",research); self.step(job_id,"research","completed","公司研究已完成" if research["results"] else "无外部研究结果，已记录降级模式")
        self.step(job_id,"review","running","独立 Reviewer 正在审查初稿"); review=self.docs.review(job,evaluation,research,cv,cover); self.ctx.write_json(root/"review.json",review); self.step(job_id,"review","completed","Reviewer 已返回修改意见")
        self.step(job_id,"revise","running","正在应用复审意见"); cv,cover,revision=self.docs.revise(job,evaluation,research,review,cv,cover); self.ctx.write_json(root/"revision_notes.json",revision); self.step(job_id,"revise","completed","修订稿已生成")
        cv_dir,cover_dir,cv_path,cover_path=self.pdf.prepare(root,job,cv,cover)
        self.step(job_id,"compile","running","正在编译并自动修复"); compile_report,visual,cv,cover=self.pdf.compile_visual_loop(job,evaluation,cv_path,cover_path,cv,cover); self.ctx.write_json(root/"compile_report.json",compile_report); self.step(job_id,"compile","completed","CV=2页，求职信=1页")
        self.ctx.write_json(root/"visual_report.json",visual); self.step(job_id,"visual","completed","PDF 视觉检查通过")
        self.step(job_id,"ats","running","正在检查 ATS 文本层和关键词"); ats=self.pdf.ats(job,evaluation,cv_path.with_suffix('.pdf'),cv)
        if ats.get("missing_have_it"):
            cv=self.pdf.repair_ats(job,evaluation,cv,ats); cv_path.write_text(cv,encoding="utf-8"); compile_report,visual,cv,cover=self.pdf.compile_visual_loop(job,evaluation,cv_path,cover_path,cv,cover); ats=self.pdf.ats(job,evaluation,cv_path.with_suffix('.pdf'),cv)
        self.ctx.write_json(root/"ats_report.json",ats); self.step(job_id,"ats","completed","ATS 检查完成")
        self.step(job_id,"verify","running","正在执行最终唯一一次完整核验"); report=self.docs.final_verify(job,evaluation,research,review,revision,cv,cover,compile_report,visual,ats)
        self.ctx.write_json(root/"final_report.json",report); (root/"final_report.md").write_text(self.markdown(job,report),encoding="utf-8"); self.pdf.cleanup(cv_dir); self.pdf.cleanup(cover_dir); bundle=self.bundle(root); report["bundle"]=bundle.name; self.ctx.write_json(root/"final_report.json",report); self.update(job_id,result_json=json.dumps(report,ensure_ascii=False))
        if STRICT and not report.get("overall_pass"): raise RuntimeError("最终核验未通过，请下载 final_report.json 查看失败项")
        self.step(job_id,"verify","completed","最终核验报告和下载包已生成"); self.update(job_id,status="completed",current_step=None,result_json=json.dumps(report,ensure_ascii=False),error=None)
    def get(self,job_id):
        row=self.row(job_id)
        return {"id":row["id"],"status":row["status"],"current_step":row["current_step"],"job":self.decode(row["job_json"]),"evaluation":self.decode(row["evaluation_json"]),"steps":self.decode(row["steps_json"]),"result":self.decode(row["result_json"]),"error":row["error"],"created_at":row["created_at"],"updated_at":row["updated_at"],"artifacts":self.artifacts(job_id)}
    def artifacts(self,job_id):
        row=self.row(job_id); root=Path(row["artifact_dir"]) if row["artifact_dir"] else None
        if not root or not root.exists(): return []
        return [{"name":p.relative_to(root).as_posix(),"size":p.stat().st_size} for p in sorted(root.rglob('*')) if p.is_file() and p.suffix.lower() not in {'.aux','.log','.out'}]
    def artifact_path(self,job_id,name):
        row=self.row(job_id)
        if not row["artifact_dir"]: raise FileNotFoundError(name)
        root=Path(row["artifact_dir"]).resolve(); path=(root/name).resolve()
        if root not in path.parents or not path.is_file(): raise FileNotFoundError(name)
        return path
    def bundle(self,root):
        target=root/"application_bundle.zip"
        with zipfile.ZipFile(target,"w",zipfile.ZIP_DEFLATED) as z:
            for p in root.rglob('*'):
                if p.is_file() and p!=target and p.suffix.lower() not in {'.aux','.log','.out'} and 'render_' not in p.name:z.write(p,p.relative_to(root))
        return target
    def markdown(self,job,report):
        lines=[f"# Application Verification - {job.get('company','')} / {job.get('title','')}","",f"Overall pass: **{report.get('overall_pass')}**","","## Key tailoring decisions"]+[f"- {x}" for x in report.get("key_tailoring_decisions",[])]+["","## Acknowledged gaps"]+[f"- {x}" for x in report.get("acknowledged_gaps",[])]
        for cat,items in (report.get("verification") or {}).items():
            lines += ["",f"### {cat}"]+[f"- [{'PASS' if x.get('pass') else 'FAIL'}] {x.get('item','')}: {x.get('note','')}" for x in items]
        return "\n".join(lines)+"\n"

manager=FullApplyManager()
