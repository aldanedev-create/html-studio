# HTML Studio

HTML Studio is a friendly, native-first coding studio for children and
beginners. It uses a VS Code-inspired workspace to edit real HTML, CSS, and
JavaScript files, with a live preview and bite-sized lessons. The shell is
written in Teloce-Py `.vel` files and its local API is served by Flaxon.

## Run it locally

From this directory, use the editable Teloce-Py and Flaxon checkouts:

```powershell
python -m pip install -e ..\teloce-python
python -m pip install -e ..\Flaxon-Backend-Framework-main\Flaxon-Backend-Framework-main
python -m pip install -r requirements.txt
python build.py
python app.py
```

Open <http://127.0.0.1:5179>. Edit files in `workspace/starter-site`, choose
them in the explorer, and press Run. HTML Studio discovers every supported
file in the folder; it does not use fake editor content. The preview inlines
local CSS and JavaScript so a starter project works without a separate static
web server. External CDN URLs remain available in the preview sandbox.

## Project shape

- `static/js/**/*.vel` — the HTML Studio interface, compiled by Teloce-Py.
- `static/js/adapters` — the small browser bridge for Monaco, files, and preview.
- `workspace/starter-site` — the real starter project children can edit.
- `app.py` — Flaxon file/workspace API and local development server.
- `src-tauri` — native Windows shell and safe filesystem commands.

## Windows Store packaging

Push a tag such as `v0.1.0` or manually run **Windows package** in GitHub
Actions. The workflow checks out editable Teloce-Py and Flaxon, builds the
frontend, packages the native Tauri shell, and stages an MSIX. The Store
identity configured by the workflow is:

```text
Identity Name: HappyRecorder3D.html-studio
Publisher: CN=50CA2AC2-0155-44AC-B2B0-47100A3FB6E2
Publisher display name: Happy Recorder 3D
```

The Microsoft Store signs the MSIX after it passes certification, so a private
PFX is not required for Store submission. A certificate is only needed when
you distribute the MSIX directly or install it by sideloading. See
`docs/microsoft-store.md`.

## Scope

This is a native desktop app, not a PWA. Source files are saved on disk; the
browser preview is sandboxed. IndexedDB is reserved for local UI recovery
metadata, while Flaxon owns workspace operations.
