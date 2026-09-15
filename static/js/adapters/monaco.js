(function () {
  const languageFor = (path) => {
    const ext = window.VelStudioWorkspace?.extension(path);
    return { ".html": "html", ".htm": "html", ".css": "css", ".js": "javascript", ".mjs": "javascript", ".json": "json", ".vel": "html", ".md": "markdown" }[ext] || "plaintext";
  };

  let controller;
  let editor;
  let container;
  let inputChange;
  let markerDisposable;
  let models = new Map();
  const contents = new Map();
  const savedContents = new Map();
  let openRequest = 0;
  let openQueue = Promise.resolve();
  let activePath = "";
  let neonThemeDefined = false;
  let currentTheme = "vs-dark";

  function savedTheme() {
    try {
      const value = JSON.parse(localStorage.getItem("html-studio-settings") || "{}").theme;
      return ["html-studio-dark", "neon-light", "high-contrast"].includes(value) ? value : "html-studio-dark";
    } catch (_) { return "html-studio-dark"; }
  }

  function setTheme(theme = savedTheme()) {
    const monaco = window.monaco;
    if (!monaco?.editor) return;
    if (theme === "neon-light" && !neonThemeDefined) {
      monaco.editor.defineTheme("html-studio-neon-light", {
        base: "vs", inherit: true,
        rules: [
          { token: "comment", foreground: "65758B" }, { token: "keyword", foreground: "9B2CBE" },
          { token: "string", foreground: "087F91" }, { token: "number", foreground: "B45309" },
          { token: "tag", foreground: "0B7285" }, { token: "attribute.name", foreground: "C2410C" },
        ],
        colors: { "editor.background": "#F4F8FF", "editor.foreground": "#17244A", "editorLineNumber.foreground": "#91A6C5", "editorLineNumber.activeForeground": "#087F91", "editorCursor.foreground": "#D946EF", "editor.selectionBackground": "#A5F3FC88", "editor.lineHighlightBackground": "#E5F2FF", "editorIndentGuide.background": "#D6E3F5", "editorIndentGuide.activeBackground": "#8EDCE4" },
      });
      neonThemeDefined = true;
    }
    currentTheme = theme === "neon-light" ? "html-studio-neon-light" : theme === "high-contrast" ? "hc-black" : "vs-dark";
    monaco.editor.setTheme(currentTheme);
  }

  function setStatus(text) { window.VelStudioShell?.setStatus?.(text); }
  function setEditorStatus(text) { window.VelStudioShell?.setEditorStatus?.(text); }
  function setDirty(value) { window.VelStudioShell?.setEditorDirty?.(Boolean(value)); }

  function modelUri(path) {
    const segments = String(path).split("/").filter(Boolean).map((segment) => encodeURIComponent(segment));
    return window.monaco.Uri.parse(`htmlstudio://workspace/${segments.join("/")}`);
  }

  function loadMonaco() {
    if (window.monaco?.editor) return Promise.resolve(window.monaco);
    if (typeof window.require !== "function") return Promise.reject(new Error("The local Monaco loader is missing."));
    return new Promise((resolve, reject) => {
      let settled = false;
      const finish = (callback, value) => { if (settled) return; settled = true; window.clearTimeout(timer); callback(value); };
      const timer = window.setTimeout(() => finish(reject, new Error("The local Monaco bundle took too long to load.")), 12000);
      try {
        window.require.config({ paths: { vs: "/static/vendor/monaco/vs" } });
        window.require(["vs/editor/editor.main"], () => {
          if (window.monaco?.editor) finish(resolve, window.monaco);
          else finish(reject, new Error("Monaco loaded without its editor API."));
        }, (error) => finish(reject, error));
      } catch (error) { finish(reject, error); }
    });
  }

  function queueSave() {
    if (window.VelStudioSettings?.autosave === false) return;
    window.clearTimeout(window.__htmlStudioSaveTimer);
    window.__htmlStudioSaveTimer = window.setTimeout(() => save(), 900);
  }

  async function openFile(path, request) {
    if (!editor || !path) return false;
    try {
      if (!contents.has(path)) {
        const content = await window.VelStudioWorkspace.read(path);
        contents.set(path, content);
        savedContents.set(path, content);
      }
      if (request !== openRequest || !editor) return false;
      if (!models.has(path)) models.set(path, window.monaco.editor.createModel(contents.get(path), languageFor(path), modelUri(path)));
      editor.setModel(models.get(path));
      activePath = path;
      window.VelStudioShell?.setActiveFile?.(path);
      setDirty(isDirty(path));
      window.dispatchEvent(new CustomEvent("vel-studio-open-file", { detail: path }));
      setStatus(`Editing ${path}`);
      setEditorStatus("Monaco");
      editor.focus();
      return true;
    } catch (error) { setStatus(`Open failed: ${error.message}`); setEditorStatus("Error"); return false; }
  }

  function open(path) {
    const request = ++openRequest;
    const task = () => openFile(path, request);
    const pending = openQueue.then(task, task);
    openQueue = pending.catch(() => false);
    return pending;
  }

  async function save() {
    if (!editor || !activePath) return false;
    const path = activePath;
    const content = editor.getValue();
    try {
      await window.VelStudioWorkspace.write(path, content);
      contents.set(path, content);
      savedContents.set(path, content);
      setDirty(false);
      setStatus(`Saved ${path}`);
      window.dispatchEvent(new CustomEvent("vel-studio-saved", { detail: path }));
      return true;
    } catch (error) { setStatus(`Save failed: ${error.message}`); return false; }
  }

  async function mount(containerId, state) {
    dispose();
    controller = state;
    container = document.getElementById(containerId);
    const loading = document.getElementById("local-editor-loading");
    if (!container) { setStatus("Editor could not mount: container missing."); setEditorStatus("Error"); return; }
    try {
      const monaco = await loadMonaco();
      const liveContainer = document.getElementById(containerId);
      const liveLoading = document.getElementById("local-editor-loading");
      if (!controller || !liveContainer) { setStatus("Editor could not mount: container was replaced before Monaco finished loading."); setEditorStatus("Error"); return; }
      container = liveContainer;
      liveLoading?.remove();
      setTheme(savedTheme());
      editor = monaco.editor.create(container, {
        theme: savedTheme() === "neon-light" ? "html-studio-neon-light" : savedTheme() === "high-contrast" ? "hc-black" : "vs-dark", automaticLayout: true, minimap: { enabled: false }, fontSize: 14, lineHeight: 22,
        padding: { top: 14, bottom: 14 }, scrollBeyondLastLine: false, wordWrap: "off", tabSize: 2,
        insertSpaces: true, suggestOnTriggerCharacters: true, accessibilitySupport: "on",
      });
      inputChange = editor.onDidChangeModelContent(() => {
        if (!activePath) return;
        contents.set(activePath, editor.getValue());
        setDirty(isDirty(activePath));
        setStatus("Unsaved changes · saving soon");
        queueSave();
      });
      markerDisposable = window.monaco.editor.onDidChangeMarkers((resources) => {
        const model = editor?.getModel();
        if (!model || !resources.some(resource => String(resource).includes(model.uri.path))) return;
        const count = window.monaco.editor.getModelMarkers({ resource: model.uri }).filter(marker => marker.severity === window.monaco.MarkerSeverity.Error).length;
        window.VelStudioShell?.setProblemCount?.(count);
      });
      setStatus("Monaco editor ready");
      setEditorStatus("Monaco");
      const initial = window.VelStudioShell?.activeFile || "index.html";
      const records = await window.VelStudioWorkspace.list().catch(() => []);
      const first = records.find(file => file.kind === "file" && /\.(?:html?|css|js|mjs)$/i.test(file.path));
      if (!first && !records.some(file => file.kind === "file" && file.path === initial)) {
        setStatus("No editable files in this workspace");
        setEditorStatus("Ready");
        return;
      }
      await open(records.some(file => file.path === initial) ? initial : first.path);
      editor.focus();
    } catch (error) {
      if (loading) loading.textContent = `Editor unavailable: ${error.message}`;
      setStatus(`Editor failed to load: ${error.message}`); setEditorStatus("Error");
    }
  }

  function getFiles() {
    const result = Object.fromEntries(contents.entries());
    if (editor && activePath) result[activePath] = editor.getValue();
    return result;
  }

  function isDirty(path = activePath) {
    if (!path) return false;
    const current = path === activePath && editor ? editor.getValue() : contents.get(path);
    return current !== savedContents.get(path);
  }

  function updateOptions(options) { editor?.updateOptions?.(options); }

  function revealLine(line) {
    if (!editor || !Number.isFinite(Number(line))) return;
    const target = Math.max(1, Math.min(Number(line), editor.getModel()?.getLineCount?.() || Number(line)));
    editor.revealLineInCenter(target);
    editor.setPosition({ lineNumber: target, column: 1 });
    editor.focus();
  }

  function dispose() {
    window.clearTimeout(window.__htmlStudioSaveTimer);
    window.__htmlStudioSaveTimer = undefined;
    openRequest++;
    inputChange?.dispose?.();
    markerDisposable?.dispose?.();
    inputChange = undefined;
    markerDisposable = undefined;
    editor?.dispose?.();
    editor = undefined;
    for (const model of models.values()) model.dispose();
    models.clear();
    contents.clear();
    savedContents.clear();
    activePath = "";
    container = undefined;
    controller = undefined;
  }

  window.VelStudioEditor = { mount, open, save, getFiles, isDirty, updateOptions, setTheme, revealLine, dispose, contents, theme: () => currentTheme };
})();
