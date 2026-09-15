# Native development

HTML Studio is the product name. The repository and internal Teloce globals
still use a few `vel-studio` compatibility names; those do not change the
Store display name or package identity.

Install the editable local checkouts, build the `.vel` UI, and start Flaxon:

```powershell
python -m pip install -e ..\teloce-python
python -m pip install -e ..\Flaxon-Backend-Framework-main\Flaxon-Backend-Framework-main
python -m pip install -r requirements.txt
python build.py
python app.py
```

Open `http://127.0.0.1:5179`. Source files in `workspace/starter-site` are
real files. Monaco loads them through the workspace adapter, autosaves edits,
and the Preview button renders the current in-memory content. Monaco is
packaged in the application, so the editor works without internet access.

For native development, install the Rust toolchain, Visual C++ Build Tools,
and the Tauri CLI. `cargo tauri dev` runs `python app.py` through
`beforeDevCommand`. The release build packages the frontend and starts the
Flaxon Python sidecar. Native file access is performed by the Rust bridge, not
by unrestricted browser filesystem permissions.
