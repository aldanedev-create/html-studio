(function () {
  let shell;
  let keyHandler;
  let refreshHandler;

  function status(message) { shell?.setStatus?.(message); }

  async function refreshWorkspace() {
    try {
      const records = await window.VelStudioWorkspace.list();
      const info = await window.VelStudioWorkspace.info?.().catch(() => null);
      if (info?.name) shell?.setWorkspaceName?.(info.name);
      window.dispatchEvent(new CustomEvent("vel-studio-workspace-refresh", { detail: records }));
      return records;
    } catch (error) { status(`Workspace refresh failed: ${error.message}`); return []; }
  }

  async function run() {
    if (shell?.running) return;
    shell?.setRunning?.(true);
    try {
      status("Saving before run...");
      const saved = await window.VelStudioEditor?.save?.();
      if (saved === false) return;
      status("Running preview...");
      const refreshed = await window.VelStudioPreview?.refresh?.();
      if (refreshed === false) throw new Error("The preview could not be refreshed.");
      window.VelStudioCelebration?.burst?.();
      status("Preview running");
    } catch (error) { status(`Run failed: ${error.message}`); }
    finally { shell?.setRunning?.(false); }
  }

  async function newProject() {
    const name = window.prompt("Project name", "my-website");
    if (!name) return;
    const template = (window.prompt("Template: website, blank, or playground", "website") || "website").trim().toLowerCase();
    const selected = ["website", "blank", "playground"].includes(template) ? template : "website";
    try {
      await window.VelStudioWorkspace.createProject(name.trim(), selected);
      status(`Created ${name.trim()}`);
      window.location.reload();
    } catch (error) { status(`Could not create project: ${error.message}`); }
  }

  function openQuickPick() {
    window.VelStudioWorkspace.list().then(records => {
      const files = records.filter(record => record.kind === "file").map(record => record.path);
      const chosen = window.prompt(`Open file:\n${files.join("\n")}`, shell?.activeFile || files[0] || "");
      if (chosen && files.includes(chosen.trim())) window.VelStudioEditor?.open?.(chosen.trim());
      else if (chosen) status(`File not found: ${chosen.trim()}`);
    }).catch(error => status(`Could not open file picker: ${error.message}`));
  }

  function commandPalette() {
    const commands = ["Save", "Run", "Refresh Preview", "Search Project", "Toggle Sidebar", "Toggle Bottom Panel", "Open File", "Close Active Tab"];
    const command = window.prompt(`Command Palette\n\n${commands.join("\n")}`, "Run");
    if (!command) return;
    const value = command.trim().toLowerCase();
    if (value === "save") window.VelStudioEditor?.save?.();
    else if (value === "run") run();
    else if (value === "refresh preview") window.VelStudioPreview?.refresh?.();
    else if (value === "search project") window.dispatchEvent(new CustomEvent("vel-studio-focus-search"));
    else if (value === "toggle sidebar") shell?.toggleSidebar?.();
    else if (value === "toggle bottom panel") shell?.toggleBottom?.("problems");
    else if (value === "open file") openQuickPick();
    else if (value === "close active tab") window.dispatchEvent(new CustomEvent("vel-studio-close-active"));
    else status(`Unknown command: ${command}`);
  }

  function init(instance) {
    shell = instance;
    refreshHandler = () => refreshWorkspace();
    window.addEventListener("vel-studio-request-refresh", refreshHandler);
    keyHandler = event => {
      const modifier = event.ctrlKey || event.metaKey;
      if (modifier && event.key.toLowerCase() === "s") { event.preventDefault(); window.VelStudioEditor?.save?.(); }
      else if (modifier && event.shiftKey && event.key.toLowerCase() === "p") { event.preventDefault(); commandPalette(); }
      else if (modifier && event.key.toLowerCase() === "p") { event.preventDefault(); openQuickPick(); }
      else if (modifier && event.shiftKey && event.key.toLowerCase() === "f") { event.preventDefault(); window.dispatchEvent(new CustomEvent("vel-studio-focus-search")); }
      else if (modifier && event.key.toLowerCase() === "b") { event.preventDefault(); shell.toggleSidebar(); }
      else if (modifier && event.key.toLowerCase() === "j") { event.preventDefault(); shell.toggleBottom("console"); }
      else if (modifier && event.key.toLowerCase() === "w") { event.preventDefault(); window.dispatchEvent(new CustomEvent("vel-studio-close-active")); }
      else if (event.key === "F5") { event.preventDefault(); run(); }
      else if (modifier && event.key.toLowerCase() === "r") { event.preventDefault(); window.VelStudioPreview?.refresh?.(); }
    };
    window.addEventListener("keydown", keyHandler);
    refreshWorkspace();
  }

  function dispose() {
    if (keyHandler) window.removeEventListener("keydown", keyHandler);
    if (refreshHandler) window.removeEventListener("vel-studio-request-refresh", refreshHandler);
    keyHandler = undefined; refreshHandler = undefined; shell = undefined;
  }

  window.VelStudioApp = { init, dispose, run, newProject, refreshWorkspace, openQuickPick, commandPalette };
})();
