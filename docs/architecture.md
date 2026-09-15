# HTML Studio architecture

HTML Studio is a native Windows coding studio with a Teloce-Py interface and
a Flaxon development API. The same frontend works in a normal browser during
development and inside the Tauri WebView after packaging.

## Data flow

```text
.vel files -> Teloce-Py build -> dist/static/js/*.js -> HTML Studio shell
                                                  |
                                      workspace adapter
                                      /              \
                           Flaxon HTTP API        Tauri commands
                           (browser dev)           (native app)
                                                  |
                                      real project files on disk
```

`build.py` compiles every `.vel` file under `static/js`, uses Teloce's shared
runtime option, copies the adapters and logo assets, and writes the generated
frontend to `dist`. `app.py` runs the same build before starting Flaxon.

## Frontend layers

- `App.vel` owns the activity navigation and global editor state.
- `components/*.vel` provide the top bar, explorer, tabs, Monaco and preview
  panels.
- `pages/*.vel` provide the editor, lessons, challenges, and settings views.
- `adapters/workspace.js` selects the Flaxon HTTP API or Tauri commands.
- `adapters/monaco.js` reads and writes real files and debounces saves. Monaco
  is vendored from the pinned npm package into `static/vendor/monaco`; it is
  never loaded from a CDN at runtime.
- `adapters/preview.js` combines the selected HTML with local styles/scripts in
  a sandboxed iframe and forwards console errors to the status bar.

The `.vel` files are application code, not decorative templates. Every file is
imported by `App.vel` directly or by `EditorPage.vel` and is compiled into the
running shell.

## Security boundaries

The API and Rust commands allow only text extensions, enforce a 512 KB file
limit, reject traversal paths, and keep the preview in a sandboxed iframe.
The preview is the only place project JavaScript executes. A production
application should still treat opened folders as user-trusted code.
