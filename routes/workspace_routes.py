"""Workspace API - safely browse and work with a selected project folder."""
import io
import mimetypes
import os
import re
import secrets
import time
from urllib.parse import quote, urlencode
import zipfile

from fastapi import APIRouter, Request, HTTPException, Query
from fastapi.responses import Response, StreamingResponse

from src.auth_helpers import get_current_user
from src.tool_security import owner_is_admin_or_single_user

# Cap entries returned per directory (mirrors filesystem_tools._CODENAV_MAX_HITS).
# A huge directory shouldn't dump thousands of rows into the picker; the user can
# type/paste a path to jump straight in instead.
_MAX_BROWSE_DIRS = 500
_MAX_PROJECT_FILES = 5000
_MAX_FILE_BYTES = 2 * 1024 * 1024
_MAX_DOWNLOAD_BYTES = 100 * 1024 * 1024
_SAFE_HIDDEN_FILES = frozenset({".gitignore", ".nojekyll"})
_PREVIEW_EXTENSIONS = frozenset({
    ".html", ".htm", ".css", ".js", ".mjs", ".json", ".svg", ".png", ".jpg",
    ".jpeg", ".gif", ".webp", ".ico", ".avif", ".woff", ".woff2", ".ttf",
    ".otf", ".mp3", ".wav", ".mp4", ".webm", ".ogg",
})
_PREVIEW_TOKEN_TTL = 10 * 60
_preview_tokens = {}


def _require_workspace(request: Request, raw_path: str):
    """Apply the route gate and return a canonical, non-root workspace."""
    owner = get_current_user(request)
    if not owner_is_admin_or_single_user(owner):
        raise HTTPException(status_code=403, detail="Project workspace access is admin-only")
    from src.tool_execution import vet_workspace
    workspace = vet_workspace(raw_path)
    if workspace is None:
        raise HTTPException(status_code=400, detail="Invalid or unavailable workspace")
    return workspace


def _safe_project_path(workspace: str, raw_path: str, *, must_exist=True):
    """Resolve a workspace-relative path and reject links, secrets and traversal."""
    from src.tool_execution import _is_sensitive_path, _resolve_tool_path_in_workspace

    if not isinstance(raw_path, str) or not raw_path.strip():
        raise HTTPException(status_code=400, detail="File path is required")
    try:
        resolved = _resolve_tool_path_in_workspace(workspace, raw_path)
    except TypeError:
        raise HTTPException(status_code=400, detail="Path is outside the workspace")
    except ValueError as exc:
        if "sensitive" in str(exc).casefold():
            raise HTTPException(status_code=403, detail="Sensitive workspace path is not accessible")
        raise HTTPException(status_code=400, detail="Path is outside the workspace")
    if resolved == os.path.realpath(workspace) or _is_sensitive_path(resolved):
        raise HTTPException(status_code=403, detail="Sensitive workspace path is not accessible")
    # Do not follow links: a link can be swapped after validation and can point
    # outside the selected project.
    if os.path.islink(resolved):
        raise HTTPException(status_code=403, detail="Symbolic links are not accessible")
    if must_exist and not os.path.isfile(resolved):
        raise HTTPException(status_code=404, detail="File not found")
    return resolved


def _safe_entry(path: str, workspace: str) -> bool:
    """Whether a directory entry is suitable for a project listing/download."""
    from src.tool_execution import _is_sensitive_path

    if os.path.islink(path) or _is_sensitive_path(os.path.realpath(path)):
        return False
    try:
        relative = os.path.relpath(path, workspace)
    except ValueError:
        return False
    parts = relative.replace("\\", "/").split("/")
    if any(part.casefold() == ".git" for part in parts):
        return False
    for part in parts:
        if part.startswith(".") and part.casefold() not in _SAFE_HIDDEN_FILES:
            return False
    name = parts[-1].casefold()
    if name.endswith((".pem", ".key", ".p12", ".pfx")):
        return False
    if name in {"credentials", "credentials.json", "secrets", "secrets.json"}:
        return False
    if name.startswith(".env"):
        return False
    return True


def _relative_path(path: str, workspace: str) -> str:
    return os.path.relpath(path, workspace).replace("\\", "/")


def _read_text_file(path: str) -> str:
    try:
        size = os.path.getsize(path)
    except OSError:
        raise HTTPException(status_code=404, detail="File not found")
    if size > _MAX_FILE_BYTES:
        raise HTTPException(status_code=413, detail="File is too large to edit")
    try:
        with open(path, "rb") as handle:
            data = handle.read(_MAX_FILE_BYTES + 1)
    except OSError:
        raise HTTPException(status_code=404, detail="File not found")
    if len(data) > _MAX_FILE_BYTES or b"\x00" in data:
        raise HTTPException(status_code=415, detail="Only small UTF-8 text files are supported")
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=415, detail="Only UTF-8 text files are supported")


def _issue_preview_token(workspace: str) -> str:
    now = time.monotonic()
    for token, (_, expires) in list(_preview_tokens.items()):
        if expires <= now:
            _preview_tokens.pop(token, None)
    token = secrets.token_urlsafe(32)
    _preview_tokens[token] = (workspace, now + _PREVIEW_TOKEN_TTL)
    return token


def _preview_token_workspace(token: str):
    record = _preview_tokens.get(token)
    if not record:
        return None
    workspace, expires = record
    if expires <= time.monotonic():
        _preview_tokens.pop(token, None)
        return None
    return workspace


def setup_workspace_routes():
    router = APIRouter(prefix="/api/workspace", tags=["workspace"])

    @router.get("/browse")
    def browse(request: Request, path: str = Query(default="")):
        """List subdirectories of `path` (default: home) so the UI can navigate
        the server filesystem and pick a workspace folder. Directories only.

        ADMIN-ONLY: this enumerates the server filesystem, so it is gated the
        same way the file/shell tools are (read_file/write_file/bash are in
        NON_ADMIN_BLOCKED_TOOLS). A non-admin who can't use those tools must not
        be able to map the host's directory tree either.
        """
        owner = get_current_user(request)
        if not owner_is_admin_or_single_user(owner):
            raise HTTPException(status_code=403, detail="Workspace browsing is admin-only")

        # Resolve symlinks so the reported path is canonical and the UI navigates
        # real directories (defends against symlink games in displayed paths).
        target = os.path.realpath(os.path.expanduser(path.strip() or "~"))
        if not os.path.isdir(target):
            target = os.path.realpath(os.path.expanduser("~"))

        dirs = []
        try:
            with os.scandir(target) as it:
                for entry in it:
                    try:
                        # Don't follow symlinks when classifying - a symlinked
                        # dir is skipped rather than letting the browser wander
                        # off via a link. Hidden entries are omitted.
                        if entry.is_dir(follow_symlinks=False) and not entry.name.startswith("."):
                            # Build the child path server-side with os.path.join
                            # so it's correct on Windows (backslashes) and Linux.
                            dirs.append({"name": entry.name, "path": os.path.join(target, entry.name)})
                    except OSError:
                        continue
        except (PermissionError, OSError):
            dirs = []

        dirs_sorted = sorted(dirs, key=lambda d: d["name"].lower())
        truncated = len(dirs_sorted) > _MAX_BROWSE_DIRS
        parent = os.path.dirname(target)
        from src.tool_execution import vet_workspace
        return {
            "path": target,
            "parent": parent if parent and parent != target else None,
            "dirs": dirs_sorted[:_MAX_BROWSE_DIRS],
            "truncated": truncated,
            # Whether this directory may be bound as a workspace (filesystem
            # roots and sensitive dirs may be browsed through but not chosen).
            "selectable": vet_workspace(target) is not None,
        }

    @router.get("/vet")
    def vet(request: Request, path: str = Query(default="")):
        """Validate a workspace path without binding it.

        The UI calls this before persisting a manually typed path (/workspace
        set) so a typo, file path, deleted folder, sensitive dir, or filesystem
        root is rejected up front with the canonical path returned on success,
        instead of being stored client-side and silently dropped at chat time.
        Admin-gated like /browse: it confirms path existence on the host.
        """
        owner = get_current_user(request)
        if not owner_is_admin_or_single_user(owner):
            raise HTTPException(status_code=403, detail="Workspace selection is admin-only")
        from src.tool_execution import vet_workspace
        resolved = vet_workspace(path)
        return {"ok": resolved is not None, "path": resolved}

    @router.get("/files")
    def list_project_files(
        request: Request,
        workspace: str = Query(..., min_length=1),
    ):
        """List ordinary project files, never links or sensitive metadata."""
        root = _require_workspace(request, workspace)
        files = []
        truncated = False
        pending = [root]
        while pending and len(files) < _MAX_PROJECT_FILES:
            directory = pending.pop()
            try:
                entries = list(os.scandir(directory))
            except (OSError, PermissionError):
                continue
            for entry in entries:
                full_path = entry.path
                if not _safe_entry(full_path, root):
                    continue
                try:
                    if entry.is_dir(follow_symlinks=False):
                        pending.append(full_path)
                    elif entry.is_file(follow_symlinks=False):
                        files.append({
                            "path": _relative_path(full_path, root),
                            "size": entry.stat(follow_symlinks=False).st_size,
                        })
                except OSError:
                    continue
                if len(files) >= _MAX_PROJECT_FILES:
                    truncated = True
                    break
        files.sort(key=lambda item: item["path"].casefold())
        return {
            "workspace": root,
            "files": files,
            # A simple path list keeps the response convenient for API clients.
            "paths": [item["path"] for item in files],
            "truncated": truncated,
        }

    @router.get("/file")
    def read_project_file(
        request: Request,
        workspace: str = Query(..., min_length=1),
        path: str = Query(..., min_length=1),
    ):
        root = _require_workspace(request, workspace)
        resolved = _safe_project_path(root, path)
        if not _safe_entry(resolved, root):
            raise HTTPException(status_code=403, detail="Sensitive workspace path is not accessible")
        return {
            "workspace": root,
            "path": _relative_path(resolved, root),
            "content": _read_text_file(resolved),
        }

    async def _update_project_file(request: Request):
        root = None
        try:
            payload = await request.json()
        except Exception:
            raise HTTPException(status_code=400, detail="JSON body is required")
        if not isinstance(payload, dict):
            raise HTTPException(status_code=400, detail="JSON object is required")
        workspace = payload.get("workspace") or payload.get("workspace_path")
        path = payload.get("path")
        content = payload.get("content")
        root = _require_workspace(request, workspace)
        if not isinstance(content, str):
            raise HTTPException(status_code=422, detail="content must be a string")
        if len(content.encode("utf-8")) > _MAX_FILE_BYTES or "\x00" in content:
            raise HTTPException(status_code=413, detail="Only small UTF-8 text files can be edited")
        resolved = _safe_project_path(root, path)
        if not _safe_entry(resolved, root):
            raise HTTPException(status_code=403, detail="Sensitive workspace path is not accessible")
        # Re-check immediately before writing to narrow symlink replacement races.
        if os.path.islink(resolved) or not os.path.isfile(resolved):
            raise HTTPException(status_code=403, detail="File is no longer a regular workspace file")
        try:
            with open(resolved, "w", encoding="utf-8", newline="") as handle:
                handle.write(content)
        except OSError:
            raise HTTPException(status_code=500, detail="Could not save file")
        return {"ok": True, "workspace": root, "path": _relative_path(resolved, root)}

    # PUT is the public API; PATCH is accepted for clients that model editing
    # as a partial resource update.
    router.add_api_route("/file", _update_project_file, methods=["PUT", "PATCH"])

    @router.get("/download")
    def download_project(
        request: Request,
        workspace: str = Query(..., min_length=1),
    ):
        """Download a bounded zip containing only safe regular project files."""
        root = _require_workspace(request, workspace)
        buffer = io.BytesIO()
        total = 0
        count = 0
        with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            pending = [root]
            while pending:
                directory = pending.pop()
                try:
                    entries = list(os.scandir(directory))
                except (OSError, PermissionError):
                    continue
                for entry in entries:
                    if not _safe_entry(entry.path, root):
                        continue
                    try:
                        if entry.is_dir(follow_symlinks=False):
                            pending.append(entry.path)
                        elif entry.is_file(follow_symlinks=False):
                            size = entry.stat(follow_symlinks=False).st_size
                            if size > _MAX_DOWNLOAD_BYTES - total:
                                raise HTTPException(status_code=413, detail="Workspace download is too large")
                            archive.write(entry.path, _relative_path(entry.path, root))
                            total += size
                            count += 1
                            if count > _MAX_PROJECT_FILES:
                                raise HTTPException(status_code=413, detail="Workspace contains too many files")
                    except OSError:
                        continue
        buffer.seek(0)
        return StreamingResponse(
            buffer,
            media_type="application/zip",
            headers={
                "Content-Disposition": 'attachment; filename="project-workspace.zip"',
                "Cache-Control": "no-store",
            },
        )

    def _preview_file(request: Request, workspace: str, file_path: str, token: str = ""):
        token_workspace = _preview_token_workspace(token) if token else None
        if token_workspace:
            # The token is a short-lived capability issued only after the
            # authenticated HTML request. Do not trust a caller-supplied
            # workspace alongside it.
            root = token_workspace
        else:
            root = _require_workspace(request, workspace)
        resolved = _safe_project_path(root, file_path)
        if not _safe_entry(resolved, root):
            raise HTTPException(status_code=403, detail="Sensitive workspace path is not accessible")
        suffix = os.path.splitext(resolved)[1].casefold()
        if suffix not in _PREVIEW_EXTENSIONS:
            raise HTTPException(status_code=415, detail="File type is not previewable")
        try:
            with open(resolved, "rb") as handle:
                data = handle.read(_MAX_FILE_BYTES + 1)
        except OSError:
            raise HTTPException(status_code=404, detail="File not found")
        if len(data) > _MAX_FILE_BYTES:
            raise HTTPException(status_code=413, detail="Preview file is too large")
        media_type = mimetypes.guess_type(resolved)[0] or "application/octet-stream"
        headers = {
            "X-Content-Type-Options": "nosniff",
            # CSP sandbox gives the preview an opaque origin; cross-origin CORP
            # lets its own static assets load despite that origin.
            "Cross-Origin-Resource-Policy": "cross-origin",
            "Referrer-Policy": "no-referrer",
            "Cache-Control": "no-store",
        }
        if suffix in {".html", ".htm"}:
            if not token:
                # Keep the initial response a normal 200 while carrying the
                # short-lived capability into relative asset URLs. Without
                # this, a CSP-sandboxed document's opaque origin cannot send
                # the browser's session cookie on asset requests.
                issued = _issue_preview_token(root)
                preview_path = file_path.replace("\\", "/")
                directory = preview_path.rsplit("/", 1)[0] + "/" if "/" in preview_path else ""
                base_url = (
                    f"/api/workspace/preview/{quote(directory, safe='/')}?"
                    f"{urlencode({'workspace': root, 'token': issued})}"
                )
                base_tag = f'<base href="{base_url}">'
                try:
                    html = data.decode("utf-8")
                except UnicodeDecodeError:
                    raise HTTPException(status_code=415, detail="HTML preview must be UTF-8")
                head = re.search(r"<head\b[^>]*>", html, re.IGNORECASE)
                data = (
                    html[:head.end()] + base_tag + html[head.end():]
                    if head else base_tag + html
                ).encode("utf-8")
            # The preview is untrusted user/project code. Sandboxing gives it an
            # opaque origin, preventing access to GepLex cookies and API routes.
            headers["Content-Security-Policy"] = (
                "default-src 'self' data: blob:; script-src 'self' 'unsafe-inline'; "
                "style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; "
                "font-src 'self' data:; connect-src 'none'; frame-src 'none'; "
                "object-src 'none'; base-uri 'self'; form-action 'none'; "
                "frame-ancestors 'self'; sandbox allow-scripts"
            )
        return Response(content=data, media_type=media_type, headers=headers)

    @router.get("/preview")
    def preview_index(
        request: Request,
        workspace: str = Query(..., min_length=1),
        path: str = Query(default="index.html"),
        token: str = Query(default=""),
    ):
        return _preview_file(request, workspace, path, token)

    @router.get("/preview/{file_path:path}")
    def preview_asset(
        request: Request,
        file_path: str,
        workspace: str = Query(..., min_length=1),
        token: str = Query(default=""),
    ):
        return _preview_file(request, workspace, file_path, token)

    return router
