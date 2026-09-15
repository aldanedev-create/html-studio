(function () {
  let iframe;
  let messageHandler;
  let mountedId;
  let refreshGeneration = 0;
  const loadedFiles = new Map();

  function report(message, level = "info") {
    const state = window.VelStudioShell;
    if (state) {
      state.previewStatus = message;
      state.consoleLines = [...(state.consoleLines || []).slice(-30), `${level}: ${message}`];
      if (level === "error") state.problemCount = Number(state.problemCount || 0) + 1;
    }
  }

  function normalize(path) { return String(path || "").replace(/^\.\//, "").replace(/^\//, "").split("?")[0].split("#")[0]; }

  function resolveLocal(source, base = "") {
    const value = String(source || "").trim();
    if (!value || /^(?:[a-z]+:|\/\/|data:|#)/i.test(value)) return null;
    const parts = `${base}/${value}`.split("/");
    const result = [];
    for (const part of parts) { if (!part || part === ".") continue; if (part === "..") result.pop(); else result.push(part); }
    return normalize(result.join("/"));
  }

  function safeScript(value) { return String(value).replace(/<\/script/gi, "<\\/script"); }

  function instrument(html) {
    const script = `<script>(function(){const send=(level,args)=>parent.postMessage({type:'vel-studio-console',level,message:args.map(item=>{try{return typeof item==='string'?item:JSON.stringify(item)}catch(_){return String(item)}}).join(' ')},'*');['log','info','warn','error'].forEach(kind=>{const old=console[kind];console[kind]=function(){send(kind,[...arguments]);old&&old.apply(console,arguments)}});window.addEventListener('error',event=>send('error',[event.message+' at '+event.filename+':'+event.lineno]));window.addEventListener('unhandledrejection',event=>send('error',['Unhandled promise rejection',event.reason]));})();<\/script>`;
    if (/<head(?:\s[^>]*)?>/i.test(html)) return html.replace(/<head(\s[^>]*)?>/i, `$&${script}`);
    return html.replace(/<html(?:\s[^>]*)?>/i, `$&<head>${script}</head>`);
  }

  function render(files) {
    loadedFiles.clear();
    for (const [path, value] of Object.entries(files || {})) loadedFiles.set(normalize(path), String(value));
    const html = loadedFiles.get("index.html") || "<!doctype html><html><head></head><body></body></html>";
    const pageBase = "";
    let output = html;
    let linkedStyles = 0;
    let linkedScripts = 0;
    output = output.replace(/<link\b([^>]*?)\bhref=["']([^"']+)["']([^>]*)>/gi, (tag, before, href, after) => {
      const path = resolveLocal(href, pageBase);
      if (!path || !/stylesheet/i.test(tag)) return tag;
      const css = loadedFiles.get(path);
      if (css === undefined) return tag;
      linkedStyles += 1;
      return `<style data-vel-source="${path}">\n${css}\n</style>`;
    });
    output = output.replace(/<script\b([^>]*?)\bsrc=["']([^"']+)["']([^>]*)>\s*<\/script>/gi, (tag, before, src, after) => {
      const path = resolveLocal(src, pageBase);
      if (!path) return tag;
      const code = loadedFiles.get(path);
      if (code === undefined) return tag;
      linkedScripts += 1;
      const attributes = `${before}${after}`.replace(/\s+src=["'][^"']+["']/i, "");
      const isModule = /\btype=["']module["']/i.test(attributes);
      const executable = isModule ? code : `(() => {\n${code}\n})();`;
      return `<script${attributes} data-vel-source="${path}">\n${safeScript(executable)}\n<\/script>`;
    });
    if (linkedStyles === 0) {
      const fallback = loadedFiles.get("styles.css");
      if (fallback !== undefined) output = output.replace(/<\/head>/i, `<style data-vel-source="styles.css">\n${fallback}\n</style></head>`);
    }
    if (linkedScripts === 0) {
      const fallback = loadedFiles.get("app.js");
      if (fallback !== undefined) output = output.replace(/<\/body>/i, `<script data-vel-source="app.js">\n(() => {\n${safeScript(fallback)}\n})();\n<\/script></body>`);
    }
    return instrument(output);
  }

  function mount(iframeId) {
    refreshGeneration += 1;
    mountedId = iframeId;
    iframe = document.getElementById(iframeId);
    if (iframe && iframeId === "challenge-preview-frame") {
      const host = document.querySelector(".preview-illustration");
      if (host) {
        iframe.hidden = false;
        iframe.style.display = "block";
      }
    }
    // The learning room reuses the preview card. The static frame is moved
    // into the visible card at mount time so both preview surfaces use the
    // same renderer and message lifecycle.
    if (!iframe && iframeId === "challenge-preview-frame") {
      const host = document.querySelector(".preview-illustration");
      if (host) {
        iframe = document.createElement("iframe");
        iframe.id = iframeId;
        iframe.title = "Challenge website preview";
        iframe.setAttribute("sandbox", "allow-scripts");
        host.replaceChildren(iframe);
      }
    }
    if (!iframe) return false;
    if (iframe) iframe.srcdoc = '<!doctype html><html><body style="margin:0;display:grid;place-items:center;min-height:100vh;font:14px system-ui;color:#65748b;background:#f7fbff">Preparing preview…</body></html>';
    if (messageHandler) window.removeEventListener("message", messageHandler);
    messageHandler = event => { if (event.data?.type === "vel-studio-console") report(event.data.message, event.data.level); };
    window.addEventListener("message", messageHandler);
    return Boolean(iframe);
  }

  async function workspaceFiles(generation) {
    const files = { ...(window.VelStudioEditor?.getFiles?.() || {}) };
    const workspace = window.VelStudioWorkspace;
    if (!workspace?.list || !workspace?.read) return files;
    const records = await workspace.list();
    for (const record of records) {
      if (generation !== refreshGeneration) break;
      if (!record?.path || files[record.path] !== undefined) continue;
      if (/\.(?:html?|css|js|mjs)$/i.test(record.path)) {
        try { files[record.path] = await workspace.read(record.path); } catch (_) { if (generation !== refreshGeneration) break; }
      }
    }
    return files;
  }

  async function refresh() {
    if (!iframe) return false;
    const generation = ++refreshGeneration;
    try {
      const state = window.VelStudioShell;
      if (state) { state.consoleLines = []; state.problemCount = 0; }
      const files = await workspaceFiles(generation);
      if (generation !== refreshGeneration || !iframe) return false;
      iframe.srcdoc = render(files);
      report("Preview refreshed");
      return true;
    } catch (error) { report(`Preview failed: ${error.message}`, "error"); return false; }
  }

  function setDevice(device) {
    if (!iframe) return;
    iframe.dataset.device = device;
    iframe.style.width = device === "mobile" ? "390px" : device === "tablet" ? "768px" : "100%";
    iframe.style.maxWidth = "100%";
  }

  function dispose(expectedId) { if (expectedId && mountedId && expectedId !== mountedId) return; refreshGeneration += 1; const oldId = mountedId; if (messageHandler) window.removeEventListener("message", messageHandler); if (oldId === "challenge-preview-frame" && iframe?.id === oldId && document.body) { iframe.hidden = true; iframe.style.display = "none"; document.body.appendChild(iframe); } messageHandler = undefined; iframe = undefined; mountedId = undefined; loadedFiles.clear(); }

  window.VelStudioPreview = { mount, refresh, render, setDevice, dispose };
})();
