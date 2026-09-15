# Editable Teloce and Flaxon builds in GitHub Actions

HTML Studio is built against the source checkouts of both framework packages. This is the same editable workflow used locally, but performed on a clean Windows runner:

```yaml
- uses: actions/checkout@v4
  with:
    repository: flaxon-labs/teloce-py
    path: teloce-python
- uses: actions/checkout@v4
  with:
    repository: Flaxon-Labs/flaxon
    path: flaxon
- run: python -m pip install -e ../teloce-python -e ../flaxon
```

The HTML Studio workflow then runs `python build.py`. Teloce compiles every `.vel` file into the `dist/static/js` tree and uses the shared runtime. Flaxon is installed editable so the app’s Python APIs and native build checks exercise the checked-out framework source.

The workflow is in `.github/workflows/build-msix.yml`. It builds the Tauri executable, generates the store icons, writes an MSIX manifest with the reserved identity `HappyRecorder3D.html-studio`, and uploads `HTML-Studio.msix` as an artifact.

## Release and signing

Run the workflow manually or push a `v*` tag. The artifact is unsigned unless the repository has these Actions secrets:

- `MSIX_PFX_BASE64`: base64-encoded PFX certificate
- `MSIX_PFX_PASSWORD`: PFX password

The certificate’s subject must match `CN=50CA2AC2-0155-44AC-B2B0-47100A3FB6E2`. For Microsoft Store submission, use the package identity reserved for the product and validate the resulting artifact in Partner Center before release.
