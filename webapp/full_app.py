"""Web entry point that layers the complete /apply pipeline onto the MVP app."""
from __future__ import annotations

from fastapi import Depends, HTTPException
from fastapi.responses import FileResponse

from webapp.main import app, require_auth
from webapp.full_apply import FullApplyRequest, manager

# webapp.main registers its SPA catch-all before this module is imported.
# Move it behind the new GET API routes so /api/full-apply/* is not swallowed.
_spa_catch_all = next(
    (route for route in list(app.router.routes) if getattr(route, "path", None) == "/{full_path:path}"),
    None,
)
if _spa_catch_all is not None:
    app.router.routes.remove(_spa_catch_all)


@app.post("/api/full-apply/evaluate")
async def full_apply_evaluate(payload: FullApplyRequest, _: str = Depends(require_auth)):
    try:
        return manager.evaluate(payload)
    except RuntimeError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/full-apply/{job_id}/confirm")
async def full_apply_confirm(job_id: int, _: str = Depends(require_auth)):
    try:
        return manager.confirm(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/full-apply/{job_id}")
async def full_apply_status(job_id: int, _: str = Depends(require_auth)):
    try:
        return manager.get(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/full-apply/{job_id}/artifacts")
async def full_apply_artifacts(job_id: int, _: str = Depends(require_auth)):
    try:
        manager.get(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"items": manager.artifacts(job_id)}


@app.get("/api/full-apply/{job_id}/download/{name:path}")
async def full_apply_download(job_id: int, name: str, _: str = Depends(require_auth)):
    try:
        path = manager.artifact_path(job_id, name)
    except (KeyError, FileNotFoundError) as exc:
        raise HTTPException(status_code=404, detail="文件不存在") from exc
    return FileResponse(path, filename=path.name)


if _spa_catch_all is not None:
    app.router.routes.append(_spa_catch_all)


if __name__ == "__main__":
    import os
    import uvicorn
    uvicorn.run("webapp.full_app:app", host="0.0.0.0", port=int(os.getenv("SERVER_PORT", "8000")), reload=False)
