# Testing

Run the project tests without unrelated globally installed pytest plugins:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = '1'
python -m pytest -q
```

The Chromium test covers initial mounting, locally bundled Monaco loading,
preview rendering, page navigation, resource filtering, settings reactivity,
file selection, and browser error capture. It deliberately waits for DOM
readiness instead of network-idle and asserts that no Monaco CDN is used.

Validate generated output as well:

```powershell
python build.py
Get-ChildItem dist -Recurse -Filter *.js | ForEach-Object { node --check $_.FullName }
```

If a compiler change is made in editable mode, the build signature in
`dist/manifest.json` invalidates stale incremental output automatically.
