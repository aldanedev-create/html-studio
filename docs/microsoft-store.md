# Microsoft Store packaging

HTML Studio is packaged as a native Tauri Windows application. It is not
submitted as a PWA. GitHub Actions builds the Teloce frontend, creates a
PyInstaller Flaxon sidecar, packages the Tauri application, and runs
`scripts/stage-msix.ps1` to create an unsigned MSIX staging artifact.

## Store identity

The staging manifest uses the values supplied for this product:

| Manifest field | Value |
| --- | --- |
| `Package/Identity/Name` | `HappyRecorder3D.html-studio` |
| `Package/Identity/Publisher` | `CN=50CA2AC2-0155-44AC-B2B0-47100A3FB6E2` |
| `Package/Properties/PublisherDisplayName` | `Happy Recorder 3D` |
| Display name | `HTML Studio` |

The executable is renamed to `HTMLStudio.exe` in the staging directory so the
manifest and package are self-consistent. `runFullTrust` is required because
Tauri launches a local desktop process and a Flaxon sidecar; request approval
or retain the capability only for the desktop package that needs it.

## Release steps

1. Ensure the GitHub repository can check out the `teloce-python` and Flaxon
   repositories used by `.github/workflows/windows-msix.yml`.
2. Run the workflow manually or push a `v*` tag.
3. Download the `html-studio-windows` artifact and inspect the generated
   `AppxManifest.xml` before submission.
4. Sign the MSIX with the certificate whose subject matches the Publisher
   value. An unsigned package is useful for validation but cannot be shipped
   to customers.
5. Upload the signed package to Partner Center and resolve any identity,
   capability, logo, or certificate warnings there.

The workflow deliberately does not store a signing certificate in the
repository. Configure signing in a protected release workflow when the
certificate and Store account are ready.
