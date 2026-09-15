# Microsoft Store packaging

HTML Studio is packaged as a native Tauri Windows application. It is not
submitted as a PWA. GitHub Actions builds the Teloce frontend, packages the
Tauri application, and creates an MSIX staging artifact. The current native
editor uses Tauri's Rust filesystem bridge; Flaxon is used for the editable
local development server and is not bundled as a production sidecar yet.

## Store identity

The staging manifest uses the values supplied for this product:

| Manifest field | Value |
| --- | --- |
| `Package/Identity/Name` | `HappyRecorder3D.html-studio` |
| `Package/Identity/Publisher` | `CN=50CA2AC2-0155-44AC-B2B0-47100A3FB6E2` |
| `Package/Properties/PublisherDisplayName` | `Happy Recorder 3D` |
| Display name | `HTML Studio` |

The staging executable is `html-studio.exe`. `runFullTrust` is required for
the packaged Tauri desktop process; retain the capability only for this
desktop package.

## Release steps

1. Ensure the GitHub repository can check out the `teloce-python` and Flaxon
   repositories used by `.github/workflows/build-msix.yml`.
2. Run the workflow manually or push a `v*` tag.
3. Download the `html-studio-msix` artifact and inspect the generated
   `AppxManifest.xml` before submission.
4. Upload the MSIX to Partner Center. Microsoft re-signs MSIX packages with
   a Microsoft certificate after they pass certification; you do not need to
   provide a CA-trusted PFX for Store submission.
5. Resolve any identity,
   capability, logo, or certificate warnings there.

If you also distribute the package outside the Store, configure a protected
release workflow with your own trusted signing certificate for that separate
distribution path.
