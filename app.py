"""Flaxon application for HTML Studio's local development shell."""

from __future__ import annotations

import json
import os
import re
import shutil
import sys
from html import escape as escape_html
from pathlib import Path
from typing import Any

from flaxon import Flaxon, HTMLResponse, JSONResponse, Request
from teloce.build import build_project
from teloce.compiler import compile as compile_vel


ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
DIST = ROOT / "dist"
DATA_ROOT = Path(os.getenv("VEL_STUDIO_DATA_DIR", os.getenv("LOCALAPPDATA", str(ROOT)))) / "VelStudio"
DEFAULT_WORKSPACE = (DATA_ROOT if getattr(sys, "frozen", False) else ROOT) / "workspace" / "starter-site"
TEXT_EXTENSIONS = {".html", ".htm", ".css", ".js", ".mjs", ".json", ".md", ".vel", ".txt"}
MAX_FILE_BYTES = 512 * 1024
MAX_WORKSPACE_ENTRIES = 5000
SAFE_NAME = re.compile(r"^[^\\/:*?\"<>|\x00-\x1f]+$")
WINDOWS_RESERVED_NAMES = {"CON", "PRN", "AUX", "NUL", *(f"COM{index}" for index in range(1, 10)), *(f"LPT{index}" for index in range(1, 10))}

PROJECT_TEMPLATES: dict[str, dict[str, str]] = {
    "blank": {
        "index.html": "<!doctype html>\n<html lang=\"en\">\n  <head>\n    <meta charset=\"UTF-8\">\n    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n    <title>My website</title>\n  </head>\n  <body>\n    <main>\n      <h1>Hello, web!</h1>\n      <p>Start building your idea.</p>\n    </main>\n  </body>\n</html>\n",
    },
    "website": {
        "index.html": "<!doctype html>\n<html lang=\"en\">\n  <head>\n    <meta charset=\"UTF-8\">\n    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n    <title>My first website</title>\n    <link rel=\"stylesheet\" href=\"styles.css\">\n  </head>\n  <body>\n    <main class=\"site\">\n      <p class=\"eyebrow\">MADE IN HTML STUDIO</p>\n      <h1>A small idea can become a website.</h1>\n      <p>Change this page, then press Run to see your work.</p>\n      <button id=\"hello\">Say hello</button>\n      <output id=\"message\" aria-live=\"polite\"></output>\n    </main>\n    <script src=\"app.js\"></script>\n  </body>\n</html>\n",
        "styles.css": ":root { font-family: system-ui, sans-serif; color: #e7eefb; background: #101a2b; }\nbody { min-height: 100vh; margin: 0; display: grid; place-items: center; }\n.site { width: min(42rem, calc(100% - 3rem)); padding: 3rem; border: 1px solid #2d466d; border-radius: 1rem; background: #17243a; }\n.eyebrow { color: #70e0cf; font-size: .75rem; font-weight: 800; letter-spacing: .12em; }\nbutton { padding: .7rem 1rem; border: 0; border-radius: .5rem; background: #70e0cf; color: #102033; font-weight: 800; cursor: pointer; }\n",
        "app.js": "document.querySelector('#hello')?.addEventListener('click', () => {\n  document.querySelector('#message').textContent = 'It works! JavaScript heard your click.';\n});\n",
    },
    "playground": {
        "index.html": "<!doctype html>\n<html lang=\"en\">\n  <head><meta charset=\"UTF-8\"><meta name=\"viewport\" content=\"width=device-width, initial-scale=1\"><title>JavaScript playground</title></head>\n  <body><main><h1 id=\"title\">Try an idea</h1><button id=\"change\">Change the title</button></main><script src=\"app.js\"></script></body>\n</html>\n",
        "styles.css": "body { margin: 0; min-height: 100vh; display: grid; place-items: center; background: #f3f7fb; color: #17243a; font: 1rem system-ui; } main { text-align: center; } button { padding: .7rem 1rem; cursor: pointer; }\n",
        "app.js": "const title = document.querySelector('#title');\ndocument.querySelector('#change').addEventListener('click', () => { title.textContent = 'You changed the page!'; });\n",
    },
}


def _workspace_root() -> Path:
    configured = os.getenv("VEL_STUDIO_WORKSPACE", "").strip()
    root = Path(configured).expanduser() if configured else DEFAULT_WORKSPACE
    root.mkdir(parents=True, exist_ok=True)
    return root.resolve()


WORKSPACE = _workspace_root()

if getattr(sys, "frozen", False) and not os.getenv("VEL_STUDIO_WORKSPACE") and not any(WORKSPACE.iterdir()):
    bundled_workspace = ROOT / "workspace" / "starter-site"
    if bundled_workspace.is_dir():
        shutil.copytree(bundled_workspace, WORKSPACE, dirs_exist_ok=True)


def _safe_workspace_path(relative: str) -> Path:
    if not isinstance(relative, str) or not relative.strip():
        raise ValueError("A relative workspace path is required.")
    parts = relative.replace("\\", "/").split("/")
    if any(not part or part in {".", ".."} for part in parts):
        raise ValueError("Workspace paths must contain only file or folder names.")
    normalized = "/".join(_safe_entry_name(part, "Path segment") for part in parts)
    candidate = (WORKSPACE / normalized).resolve()
    if candidate != WORKSPACE and WORKSPACE not in candidate.parents:
        raise ValueError("Workspace path escapes the selected project.")
    return candidate


def _safe_entry_name(value: Any, label: str = "Name") -> str:
    if not isinstance(value, str):
        raise ValueError(f"{label} must be text.")
    name = value.strip().replace("\\", "/")
    if (
        not name
        or name in {".", ".."}
        or "/" in name
        or len(name) > 255
        or name.endswith((".", " "))
        or name.split(".", 1)[0].upper() in WINDOWS_RESERVED_NAMES
        or not SAFE_NAME.fullmatch(name)
    ):
        raise ValueError(f"{label} contains an invalid file-system name.")
    return name


def _check_workspace_capacity() -> None:
    count = sum(1 for _ in WORKSPACE.rglob("*"))
    if count >= MAX_WORKSPACE_ENTRIES:
        raise ValueError("This workspace has reached the 5,000 item safety limit.")


def _file_record(path: Path) -> dict[str, Any]:
    return {
        "path": path.relative_to(WORKSPACE).as_posix(),
        "name": path.name,
        "kind": "folder" if path.is_dir() else "file",
        "size": path.stat().st_size if path.is_file() else 0,
    }


def _list_workspace() -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in sorted(WORKSPACE.rglob("*"), key=lambda item: (not item.is_dir(), item.as_posix().lower())):
        if len(records) >= MAX_WORKSPACE_ENTRIES:
            break
        if path.is_symlink() or any(part.startswith(".") or part in {"node_modules", "dist", "build"} for part in path.relative_to(WORKSPACE).parts):
            continue
        if path.is_dir() or path.suffix.lower() in TEXT_EXTENSIONS:
            records.append(_file_record(path))
    return records


def _json_error(message: str, status: int = 400) -> JSONResponse:
    return JSONResponse({"ok": False, "error": message}, status_code=status)


def _build_frontend() -> str | None:
    try:
        build_project(
            ROOT,
            out_dir=DIST,
            options={"dev": True, "source_maps": True, "shared_runtime": True, "static_dir": "static/js", "clean": True},
        )
        adapter_source = ROOT / "static" / "js" / "adapters"
        adapter_output = DIST / "static" / "js" / "adapters"
        if adapter_source.is_dir():
            import shutil

            shutil.copytree(adapter_source, adapter_output, dirs_exist_ok=True)
        asset_source = ROOT / "static" / "assets"
        asset_output = DIST / "static" / "assets"
        if asset_source.is_dir():
            shutil.copytree(asset_source, asset_output, dirs_exist_ok=True)
        return None
    except Exception as error:  # startup must expose a diagnostic instead of a blank page
        return str(error)


BUILD_ERROR = _build_frontend()
app = Flaxon("html-studio", debug=os.getenv("VEL_STUDIO_DEBUG", "1") == "1")
app.mount_static("/static", str(DIST / "static"), cache_control="no-cache")


@app.get("/")
async def home() -> HTMLResponse:
    html = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
    return HTMLResponse(html.replace("{{BUILD_ERROR}}", escape_html(BUILD_ERROR or "", quote=True)))


@app.get("/favicon.ico")
async def favicon() -> HTMLResponse:
    icon = (ROOT / "static" / "assets" / "favicon.svg").read_text(encoding="utf-8")
    return HTMLResponse(icon, headers={"cache-control": "public, max-age=86400"}, media_type="image/svg+xml")


@app.get("/api/health")
async def health() -> dict[str, Any]:
    return {"ok": BUILD_ERROR is None, "service": "html-studio", "workspace": str(WORKSPACE), "build_error": BUILD_ERROR}


@app.get("/api/workspace")
async def workspace() -> dict[str, Any]:
    return {"ok": True, "root": str(WORKSPACE), "name": WORKSPACE.name, "files": _list_workspace()}


@app.get("/api/file")
async def read_file(request: Request) -> JSONResponse:
    try:
        path = _safe_workspace_path(request.query.get("path", ""))
        if not path.is_file() or path.suffix.lower() not in TEXT_EXTENSIONS:
            return _json_error("Only existing text workspace files can be opened.", 404)
        if path.stat().st_size > MAX_FILE_BYTES:
            return _json_error("This file is larger than the 512 KB editor limit.", 413)
        return JSONResponse({"ok": True, "path": path.relative_to(WORKSPACE).as_posix(), "content": path.read_text(encoding="utf-8")})
    except (ValueError, OSError, UnicodeDecodeError) as error:
        return _json_error(str(error), 400)


@app.put("/api/file")
async def write_file(request: Request) -> JSONResponse:
    try:
        payload = await request.json()
        relative = payload.get("path", "")
        content = payload.get("content")
        path = _safe_workspace_path(relative)
        if path.suffix.lower() not in TEXT_EXTENSIONS:
            return _json_error("This file type is not enabled in the workspace editor.")
        if not isinstance(content, str):
            return _json_error("File content must be text.")
        encoded = content.encode("utf-8")
        if len(encoded) > MAX_FILE_BYTES:
            return _json_error("This file is larger than the 512 KB editor limit.", 413)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="")
        return JSONResponse({"ok": True, "path": path.relative_to(WORKSPACE).as_posix(), "size": len(encoded)})
    except (ValueError, OSError, UnicodeEncodeError, json.JSONDecodeError) as error:
        return _json_error(str(error), 400)


@app.post("/api/folder")
async def create_folder(request: Request) -> JSONResponse:
    try:
        payload = await request.json()
        relative = str(payload.get("path", "")).replace("\\", "/").strip("/")
        parts = relative.split("/") if relative else []
        if not parts:
            return _json_error("Folder paths may contain only safe names.")
        try:
            relative = "/".join(_safe_entry_name(part, "Folder name") for part in parts)
        except ValueError as error:
            return _json_error(str(error))
        _check_workspace_capacity()
        path = _safe_workspace_path(relative)
        if path.exists():
            return _json_error("A file or folder already exists at that path.", 409)
        path.mkdir(parents=True)
        return JSONResponse({"ok": True, "path": path.relative_to(WORKSPACE).as_posix()})
    except (ValueError, OSError, json.JSONDecodeError) as error:
        return _json_error(str(error), 400)


@app.post("/api/file/rename")
async def rename_workspace_entry(request: Request) -> JSONResponse:
    try:
        payload = await request.json()
        source = _safe_workspace_path(str(payload.get("path", "")))
        name = _safe_entry_name(payload.get("name"), "New name")
        if not source.exists() or source == WORKSPACE:
            return _json_error("The workspace item does not exist.", 404)
        destination = source.with_name(name)
        if destination.exists():
            return _json_error("An item with that name already exists.", 409)
        source.rename(destination)
        return JSONResponse({"ok": True, "path": destination.relative_to(WORKSPACE).as_posix()})
    except (ValueError, OSError, json.JSONDecodeError) as error:
        return _json_error(str(error), 400)


@app.delete("/api/file")
async def delete_workspace_entry(request: Request) -> JSONResponse:
    try:
        path = _safe_workspace_path(request.query.get("path", ""))
        if not path.exists() or path == WORKSPACE:
            return _json_error("The workspace item does not exist.", 404)
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
        return JSONResponse({"ok": True, "path": request.query.get("path", "")})
    except (ValueError, OSError) as error:
        return _json_error(str(error), 400)


@app.post("/api/project")
async def create_project(request: Request) -> JSONResponse:
    global WORKSPACE
    try:
        payload = await request.json()
        name = _safe_entry_name(payload.get("name"), "Project name")
        template = str(payload.get("template", "website"))
        files = PROJECT_TEMPLATES.get(template)
        if files is None:
            return _json_error("Unknown project template.")
        destination = WORKSPACE.parent / name
        if destination.exists():
            return _json_error("A project with that name already exists.", 409)
        destination.mkdir(parents=True)
        for relative, content in files.items():
            target = destination / relative
            target.write_text(content, encoding="utf-8", newline="")
        WORKSPACE = destination.resolve()
        return JSONResponse({"ok": True, "root": str(WORKSPACE), "name": WORKSPACE.name, "files": _list_workspace()})
    except (ValueError, OSError, json.JSONDecodeError) as error:
        return _json_error(str(error), 400)


@app.post("/api/project/open")
async def open_project(request: Request) -> JSONResponse:
    global WORKSPACE
    try:
        payload = await request.json()
        name = _safe_entry_name(payload.get("name"), "Project name")
        create = bool(payload.get("create", False))
        parent = WORKSPACE.parent.resolve()
        destination = (parent / name).resolve()
        if destination.parent != parent:
            return _json_error("That project path is not allowed.", 400)
        created = False
        if not destination.is_dir() and create:
            destination.mkdir(parents=False, exist_ok=True)
            created = True
        if not destination.is_dir():
            return _json_error("That project does not exist.", 404)
        WORKSPACE = destination
        return JSONResponse({"ok": True, "created": created, "root": str(WORKSPACE), "name": WORKSPACE.name, "files": _list_workspace()})
    except (ValueError, OSError, json.JSONDecodeError) as error:
        return _json_error(str(error), 400)


@app.post("/api/compile")
async def compile_source(request: Request) -> JSONResponse:
    try:
        payload = await request.json()
        source = payload.get("source", "")
        filename = payload.get("filename", "App.vel")
        if not isinstance(source, str) or len(source.encode("utf-8")) > MAX_FILE_BYTES:
            return _json_error("Source must be text under 512 KB.")
        if not isinstance(filename, str) or not filename.strip():
            filename = "App.vel"
        result = compile_vel(source, filename=filename, source_maps=True, shared_runtime_import="./teloce-runtime.js")
        return JSONResponse(
            {
                "ok": bool(result.get("success")),
                "filename": filename,
                "code": result.get("code", ""),
                "css": result.get("css", ""),
                "diagnostics": result.get("diagnostics", {}),
            },
            status_code=200 if result.get("success") else 422,
        )
    except Exception as error:
        return _json_error(f"Compiler error: {error}", 422)


@app.get("/api/resources")
async def resources() -> dict[str, Any]:
    return {
        "ok": True,
        "resources": [
            {"name": "MDN HTML", "url": "https://developer.mozilla.org/docs/Web/HTML", "kind": "Reference"},
            {"name": "MDN CSS", "url": "https://developer.mozilla.org/docs/Web/CSS", "kind": "Reference"},
            {"name": "MDN JavaScript", "url": "https://developer.mozilla.org/docs/Web/JavaScript", "kind": "Reference"},
            {"name": "JavaScript.info", "url": "https://javascript.info/", "kind": "Book"},
            {"name": "Alpine.js", "url": "https://alpinejs.dev/", "kind": "CDN library"},
            {"name": "Three.js", "url": "https://threejs.org/docs/", "kind": "CDN library"},
            {"name": "web.dev", "url": "https://web.dev/learn", "kind": "Course"},
        ],
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=os.getenv("VEL_STUDIO_HOST", "127.0.0.1"), port=int(os.getenv("VEL_STUDIO_PORT", "5179")))
