import io
import zipfile

from fastapi import FastAPI
from fastapi.testclient import TestClient

import routes.workspace_routes as workspace_routes


def _client(monkeypatch):
    monkeypatch.setattr(workspace_routes, "get_current_user", lambda request: "admin")
    monkeypatch.setattr(workspace_routes, "owner_is_admin_or_single_user", lambda owner: True)
    app = FastAPI()
    app.include_router(workspace_routes.setup_workspace_routes())
    return TestClient(app)


def test_project_files_edit_and_sensitive_paths(tmp_path, monkeypatch):
    client = _client(monkeypatch)
    (tmp_path / "index.html").write_text("<h1>old</h1>", encoding="utf-8")
    (tmp_path / "app.js").write_text("console.log(1)", encoding="utf-8")
    (tmp_path / ".env").write_text("TOKEN=do-not-return", encoding="utf-8")
    (tmp_path / "id_rsa").write_text("private", encoding="utf-8")

    root = str(tmp_path)
    listing = client.get("/api/workspace/files", params={"workspace": root})
    assert listing.status_code == 200
    assert set(listing.json()["paths"]) == {"app.js", "index.html"}

    read = client.get("/api/workspace/file", params={"workspace": root, "path": "index.html"})
    assert read.status_code == 200 and "old" in read.json()["content"]
    saved = client.put(
        "/api/workspace/file",
        json={"workspace": root, "path": "index.html", "content": "<h1>new</h1>"},
    )
    assert saved.status_code == 200
    assert (tmp_path / "index.html").read_text(encoding="utf-8") == "<h1>new</h1>"
    assert client.get(
        "/api/workspace/file",
        params={"workspace": root, "path": "../outside.txt"},
    ).status_code == 400
    assert client.get(
        "/api/workspace/file",
        params={"workspace": root, "path": ".env"},
    ).status_code == 403


def test_project_download_and_preview_are_scoped(tmp_path, monkeypatch):
    client = _client(monkeypatch)
    (tmp_path / "index.html").write_text("<script src='app.js'></script>", encoding="utf-8")
    (tmp_path / "app.js").write_text("console.log('ok')", encoding="utf-8")
    (tmp_path / ".env").write_text("SECRET=hidden", encoding="utf-8")
    root = str(tmp_path)

    download = client.get("/api/workspace/download", params={"workspace": root})
    assert download.status_code == 200
    with zipfile.ZipFile(io.BytesIO(download.content)) as archive:
        assert set(archive.namelist()) == {"app.js", "index.html"}

    preview = client.get("/api/workspace/preview/index.html", params={"workspace": root})
    assert preview.status_code == 200
    assert "sandbox allow-scripts" in preview.headers["content-security-policy"]
    assert client.get(
        "/api/workspace/preview/.env", params={"workspace": root}
    ).status_code == 403


def test_project_routes_keep_admin_gate(tmp_path, monkeypatch):
    monkeypatch.setattr(workspace_routes, "get_current_user", lambda request: "user")
    monkeypatch.setattr(workspace_routes, "owner_is_admin_or_single_user", lambda owner: False)
    app = FastAPI()
    app.include_router(workspace_routes.setup_workspace_routes())
    response = TestClient(app).get(
        "/api/workspace/files", params={"workspace": str(tmp_path)}
    )
    assert response.status_code == 403
