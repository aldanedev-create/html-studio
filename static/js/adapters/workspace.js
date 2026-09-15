(function () {
  const allowed = new Set([".html", ".htm", ".css", ".js", ".mjs", ".json", ".md", ".vel", ".txt"]);
  const MAX_FILE_BYTES = 512 * 1024;
  const MAX_ENTRIES = 5000;
  const extension = (path) => {
    const match = String(path).toLowerCase().match(/\.[^.\\/]+$/);
    return match ? match[0] : "";
  };
  let browserRoot = null;

  async function native() {
    return window.__TAURI__?.core?.invoke && window.__TAURI__?.dialog ? window.__TAURI__ : null;
  }

  function browserParts(path) {
    const parts = String(path || "").replace(/\\/g, "/").split("/");
    if (!parts.length || parts.some(part => !part || part === "." || part === "..")) throw new Error("Workspace paths must stay inside the selected folder.");
    return parts;
  }

  async function browserDirectory(parts, create = false) {
    if (!browserRoot) throw new Error("Open a folder before editing local files.");
    let directory = browserRoot;
    for (const part of parts) directory = await directory.getDirectoryHandle(part, { create });
    return directory;
  }

  async function browserExisting(directory, name) {
    try { return await directory.getFileHandle(name); }
    catch (error) {
      if (error.name !== "NotFoundError") throw error;
      try { return await directory.getDirectoryHandle(name); }
      catch (directoryError) { if (directoryError.name === "NotFoundError") return null; throw directoryError; }
    }
  }

  async function listBrowser() {
    if (!browserRoot) return [];
    const records = [];
    async function walk(directory, prefix = "") {
      for await (const [name, handle] of directory.entries()) {
        if (records.length >= MAX_ENTRIES || name.startsWith(".") || ["node_modules", "dist", "build", "target"].includes(name)) continue;
        const path = prefix ? `${prefix}/${name}` : name;
        if (handle.kind === "directory") {
          records.push({ path, name, kind: "folder", size: 0 });
          await walk(handle, path);
        } else if (allowed.has(extension(name))) {
          const file = await handle.getFile();
          records.push({ path, name, kind: "file", size: file.size });
        }
      }
    }
    await walk(browserRoot);
    return records.sort((left, right) => left.path.localeCompare(right.path, undefined, { numeric: true, sensitivity: "base" }));
  }

  async function browserFile(path, create = false) {
    const parts = browserParts(path);
    if (!allowed.has(extension(parts.at(-1)))) throw new Error("This file type is not enabled in the workspace editor.");
    const directory = await browserDirectory(parts.slice(0, -1), create);
    return directory.getFileHandle(parts.at(-1), { create });
  }

  async function list() {
    const tauri = await native();
    if (tauri) return tauri.core.invoke("workspace_list");
    if (browserRoot) return listBrowser();
    const response = await fetch("/api/workspace");
    const payload = await response.json();
    if (!response.ok || !payload.ok) throw new Error(payload.error || "Could not list workspace files");
    return payload.files;
  }

  async function read(path) {
    const tauri = await native();
    if (tauri) return tauri.core.invoke("workspace_read", { path });
    if (browserRoot) {
      const file = await (await browserFile(path)).getFile();
      if (file.size > MAX_FILE_BYTES) throw new Error("This file is larger than the 512 KB editor limit.");
      return file.text();
    }
    const response = await fetch(`/api/file?path=${encodeURIComponent(path)}`);
    const payload = await response.json();
    if (!response.ok || !payload.ok) throw new Error(payload.error || "Could not open file");
    return payload.content;
  }

  async function write(path, content) {
    const tauri = await native();
    if (tauri) return tauri.core.invoke("workspace_write", { path, content });
    if (browserRoot) {
      if (typeof content !== "string" || new Blob([content]).size > MAX_FILE_BYTES) throw new Error("This file is larger than the 512 KB editor limit.");
      const handle = await browserFile(path, true);
      const writable = await handle.createWritable();
      try { await writable.write(content); } finally { await writable.close(); }
      return { ok: true, path };
    }
    const response = await fetch("/api/file", {
      method: "PUT",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ path, content }),
    });
    const payload = await response.json();
    if (!response.ok || !payload.ok) throw new Error(payload.error || "Could not save file");
    return payload;
  }

  async function createFolder(path) {
    const tauri = await native();
    if (tauri) return tauri.core.invoke("workspace_create_folder", { path });
    if (browserRoot) {
      const parts = browserParts(path);
      const parent = await browserDirectory(parts.slice(0, -1), true);
      if (await browserExisting(parent, parts.at(-1))) throw new Error("A file or folder already exists at that path.");
      await parent.getDirectoryHandle(parts.at(-1), { create: true });
      return { ok: true, path };
    }
    const response = await fetch("/api/folder", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ path }),
    });
    const payload = await response.json();
    if (!response.ok || !payload.ok) throw new Error(payload.error || "Could not create folder");
    return payload;
  }

  async function remove(path) {
    const tauri = await native();
    if (tauri) return tauri.core.invoke("workspace_delete", { path });
    if (browserRoot) {
      const parts = browserParts(path);
      const parent = await browserDirectory(parts.slice(0, -1));
      await parent.removeEntry(parts.at(-1), { recursive: true });
      return { ok: true, path };
    }
    const response = await fetch(`/api/file?path=${encodeURIComponent(path)}`, { method: "DELETE" });
    const payload = await response.json();
    if (!response.ok || !payload.ok) throw new Error(payload.error || "Could not delete workspace item");
    return payload;
  }

  async function rename(path, name) {
    const tauri = await native();
    if (tauri) return tauri.core.invoke("workspace_rename", { path, name });
    if (browserRoot) {
      const oldParts = browserParts(path);
      const newName = String(name || "").trim();
      if (!newName || /[\\/:*?"<>|\u0000-\u001f]/.test(newName) || newName === "." || newName === "..") throw new Error("The new name contains invalid file-system characters.");
      const parent = await browserDirectory(oldParts.slice(0, -1));
      const oldHandle = await browserExisting(parent, oldParts.at(-1));
      if (!oldHandle) throw new Error("The workspace item does not exist.");
      if (await browserExisting(parent, newName)) throw new Error("An item with that name already exists.");
      const newPath = [...oldParts.slice(0, -1), newName].join("/");
      if (oldHandle.kind === "file") await write(newPath, await (await oldHandle.getFile()).text());
      else await copyBrowserDirectory(oldHandle, newPath);
      await parent.removeEntry(oldParts.at(-1), { recursive: true });
      return { ok: true, path: newPath };
    }
    const response = await fetch("/api/file/rename", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ path, name }),
    });
    const payload = await response.json();
    if (!response.ok || !payload.ok) throw new Error(payload.error || "Could not rename workspace item");
    return payload;
  }

  async function copyBrowserDirectory(source, targetPath) {
    const target = await browserDirectory(browserParts(targetPath), true);
    for await (const [name, handle] of source.entries()) {
      if (handle.kind === "directory") await copyBrowserDirectory(handle, `${targetPath}/${name}`);
      else if (allowed.has(extension(name))) await write(`${targetPath}/${name}`, await (await handle.getFile()).text());
    }
    return target;
  }

  async function createProject(name, template = "website") {
    const tauri = await native();
    if (tauri) return tauri.core.invoke("workspace_create_project", { name, template });
    if (browserRoot) {
      const projectName = String(name || "").trim();
      if (!projectName || /[\\/:*?"<>|\u0000-\u001f]/.test(projectName)) throw new Error("The project name contains invalid file-system characters.");
      let project;
      try { await browserRoot.getDirectoryHandle(projectName); throw new Error("A project with that name already exists."); } catch (error) { if (error.name !== "NotFoundError") throw error; project = await browserRoot.getDirectoryHandle(projectName, { create: true }); }
      const previous = browserRoot;
      browserRoot = project;
      const files = template === "playground" ? {
        "index.html": "<!doctype html><html lang=\"en\"><head><meta charset=\"UTF-8\"><meta name=\"viewport\" content=\"width=device-width, initial-scale=1\"><title>Playground</title><link rel=\"stylesheet\" href=\"styles.css\"></head><body><main><h1 id=\"title\">Try an idea</h1><button id=\"change\">Change the title</button></main><script src=\"app.js\"></script></body></html>\n",
        "styles.css": "body { margin: 0; min-height: 100vh; display: grid; place-items: center; font: 1rem system-ui; } main { text-align: center; }\n",
        "app.js": "document.querySelector('#change').addEventListener('click', () => { document.querySelector('#title').textContent = 'You changed the page!'; });\n",
      } : { "index.html": "<!doctype html><html lang=\"en\"><head><meta charset=\"UTF-8\"><meta name=\"viewport\" content=\"width=device-width, initial-scale=1\"><title>My website</title><link rel=\"stylesheet\" href=\"styles.css\"></head><body><main><h1>Hello, web!</h1><p>Start building your idea.</p></main><script src=\"app.js\"></script></body></html>\n", "styles.css": "body { margin: 0; min-height: 100vh; display: grid; place-items: center; font: 1rem system-ui; } main { max-width: 42rem; padding: 3rem; }\n", "app.js": "console.log('Your project is ready.');\n" };
      try { for (const [path, content] of Object.entries(files)) await write(path, content); } catch (error) { browserRoot = previous; throw error; }
      return { ok: true, name: projectName, root: projectName, files: await list() };
    }
    const response = await fetch("/api/project", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ name, template }),
    });
    const payload = await response.json();
    if (!response.ok || !payload.ok) throw new Error(payload.error || "Could not create project");
    return payload;
  }

  async function openProject(name, create = false) {
    const projectName = String(name || "").trim();
    if (!projectName || /[\\/:*?"<>|\u0000-\u001f]/.test(projectName)) throw new Error("The project name contains invalid file-system characters.");
    const tauri = await native();
    if (tauri) throw new Error("Use Open Folder to switch projects in the native app.");
    if (browserRoot) throw new Error("Project switching needs the selected folder's project root.");
    const response = await fetch("/api/project/open", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ name: projectName, create: Boolean(create) }),
    });
    const payload = await response.json();
    if (!response.ok || !payload.ok) throw new Error(payload.error || "Could not open project");
    return payload;
  }

  async function info() {
    const tauri = await native();
    if (tauri) return tauri.core.invoke("workspace_info");
    if (browserRoot) return { ok: true, name: browserRoot.name, browser: true };
    const response = await fetch("/api/workspace");
    const payload = await response.json();
    if (!response.ok || !payload.ok) throw new Error(payload.error || "Could not read workspace information");
    return payload;
  }

  async function openFolder() {
    const tauri = await native();
    if (tauri) {
      const selected = await tauri.dialog.open({ directory: true, multiple: false });
      if (!selected) return null;
      await tauri.core.invoke("workspace_set_root", { path: selected });
      return selected;
    }
    if (typeof window.showDirectoryPicker !== "function") throw new Error("Open Folder needs a Chromium browser or the native HTML Studio app.");
    browserRoot = await window.showDirectoryPicker({ mode: "readwrite" });
    return browserRoot.name;
  }

  window.VelStudioWorkspace = { allowed, extension, info, list, read, write, createFolder, remove, rename, createProject, openProject, openFolder, isBrowserWorkspace: () => Boolean(browserRoot) };
})();
