"""Filesystem API coverage for the local HTML Studio workspace."""

from __future__ import annotations

from pathlib import Path

import pytest


def test_workspace_file_lifecycle_is_scoped_and_persistent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from flaxon.testing import TestClient

    import app as html_studio

    monkeypatch.setattr(html_studio, "WORKSPACE", tmp_path.resolve())
    client = TestClient(html_studio.app)
    try:
        created = client.put("/api/file", json_data={"path": "pages/home.html", "content": "<h1>Home</h1>"})
        assert created.status_code == 200
        assert (tmp_path / "pages" / "home.html").read_text(encoding="utf-8") == "<h1>Home</h1>"

        folder = client.post("/api/folder", json_data={"path": "components"})
        assert folder.status_code == 200
        renamed = client.post("/api/file/rename", json_data={"path": "pages/home.html", "name": "index.html"})
        assert renamed.status_code == 200
        assert renamed.json()["path"] == "pages/index.html"

        listing = client.get("/api/workspace")
        assert listing.status_code == 200
        assert {entry["path"] for entry in listing.json()["files"]} >= {"pages", "pages/index.html", "components"}

        deleted = client.delete("/api/file?path=pages/index.html")
        assert deleted.status_code == 200
        assert not (tmp_path / "pages" / "index.html").exists()
    finally:
        client.close()


def test_workspace_rejects_escape_and_unsafe_names(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from flaxon.testing import TestClient

    import app as html_studio

    monkeypatch.setattr(html_studio, "WORKSPACE", tmp_path.resolve())
    client = TestClient(html_studio.app)
    try:
        assert client.put("/api/file", json_data={"path": "../outside.html", "content": "no"}).status_code == 400
        assert client.post("/api/folder", json_data={"path": "CON"}).status_code == 400
        assert client.post("/api/folder", json_data={"path": "nested/../escape"}).status_code == 400
        assert not (tmp_path.parent / "outside.html").exists()
    finally:
        client.close()


def test_new_project_creates_a_runnable_template(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from flaxon.testing import TestClient

    import app as html_studio

    root = tmp_path / "workspace"
    root.mkdir()
    monkeypatch.setattr(html_studio, "WORKSPACE", root)
    client = TestClient(html_studio.app)
    try:
        response = client.post("/api/project", json_data={"name": "hello-site", "template": "website"})
        assert response.status_code == 200
        project = tmp_path / "hello-site"
        assert (project / "index.html").is_file()
        assert (project / "styles.css").is_file()
        assert (project / "app.js").is_file()
        assert response.json()["name"] == "hello-site"
    finally:
        client.close()
