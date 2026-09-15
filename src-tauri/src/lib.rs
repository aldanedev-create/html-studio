#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use serde::Serialize;
use std::fs;
use std::path::{Component, Path, PathBuf};
use std::sync::Mutex;
use tauri::{AppHandle, Manager, State};
use tauri_plugin_shell::ShellExt;

const MAX_FILE_BYTES: u64 = 512 * 1024;
const MAX_WORKSPACE_ENTRIES: usize = 5000;

#[derive(Default)]
struct WorkspaceState(Mutex<PathBuf>);

#[derive(Serialize)]
struct FileRecord {
    path: String,
    name: String,
    kind: String,
    size: u64,
}

#[derive(Serialize)]
struct WorkspaceInfo {
    root: String,
    name: String,
}

fn allowed_extension(path: &Path) -> bool {
    matches!(
        path.extension()
            .and_then(|value| value.to_str())
            .map(|value| value.to_ascii_lowercase())
            .as_deref(),
        Some("html" | "htm" | "css" | "js" | "mjs" | "json" | "md" | "vel" | "txt")
    )
}

fn safe_entry_name(value: &str) -> Result<&str, String> {
    let name = value.trim();
    let stem = name
        .split('.')
        .next()
        .unwrap_or_default()
        .to_ascii_uppercase();
    let reserved = matches!(stem.as_str(), "CON" | "PRN" | "AUX" | "NUL")
        || (stem.starts_with("COM")
            && stem[3..]
                .parse::<u8>()
                .map(|number| (1..=9).contains(&number))
                .unwrap_or(false))
        || (stem.starts_with("LPT")
            && stem[3..]
                .parse::<u8>()
                .map(|number| (1..=9).contains(&number))
                .unwrap_or(false));
    if name.is_empty()
        || name.len() > 255
        || name == "."
        || name == ".."
        || name.ends_with('.')
        || name.ends_with(' ')
        || reserved
        || name.chars().any(|character| {
            matches!(
                character,
                '\\' | '/' | ':' | '*' | '?' | '"' | '<' | '>' | '|'
            )
        })
        || name.chars().any(|character| character.is_control())
    {
        return Err("The name contains invalid file-system characters.".into());
    }
    Ok(name)
}

fn relative_path(root: &Path, requested: &str) -> Result<PathBuf, String> {
    if requested.trim().is_empty() || requested.contains('\0') {
        return Err("A relative workspace path is required.".into());
    }
    let relative = PathBuf::from(requested.replace('\\', "/"));
    if relative.components().any(|part| {
        matches!(
            part,
            Component::Prefix(_) | Component::RootDir | Component::ParentDir
        )
    }) {
        return Err("Workspace paths must stay inside the selected folder.".into());
    }
    let candidate = root.join(relative);
    if candidate.exists() {
        let canonical_root = root.canonicalize().map_err(|error| error.to_string())?;
        let canonical_candidate = candidate
            .canonicalize()
            .map_err(|error| error.to_string())?;
        if !canonical_candidate.starts_with(&canonical_root) {
            return Err("Workspace path escapes the selected folder.".into());
        }
    } else if let Some(parent) = candidate.parent() {
        let canonical_root = root.canonicalize().map_err(|error| error.to_string())?;
        let mut existing_parent = parent.to_path_buf();
        while !existing_parent.exists() {
            if !existing_parent.pop() {
                return Err("Workspace path escapes the selected folder.".into());
            }
        }
        let canonical_parent = existing_parent
            .canonicalize()
            .map_err(|error| error.to_string())?;
        if !canonical_parent.starts_with(&canonical_root) {
            return Err("Workspace path escapes the selected folder.".into());
        }
    }
    Ok(candidate)
}

fn collect_files(root: &Path, current: &Path, records: &mut Vec<FileRecord>) -> Result<(), String> {
    if records.len() >= MAX_WORKSPACE_ENTRIES {
        return Err("This workspace has reached the 5,000 item safety limit.".into());
    }
    let entries = fs::read_dir(current).map_err(|error| error.to_string())?;
    for entry in entries {
        let entry = entry.map_err(|error| error.to_string())?;
        let path = entry.path();
        let name = entry.file_name().to_string_lossy().to_string();
        if name.starts_with('.') || name == "node_modules" || name == "target" {
            continue;
        }
        let file_type = entry.file_type().map_err(|error| error.to_string())?;
        if file_type.is_symlink() {
            continue;
        }
        if file_type.is_dir() {
            let relative = path
                .strip_prefix(root)
                .map_err(|error| error.to_string())?
                .to_string_lossy()
                .replace('\\', "/");
            records.push(FileRecord {
                path: relative,
                name,
                kind: "folder".into(),
                size: 0,
            });
            collect_files(root, &path, records)?;
            continue;
        }
        if !allowed_extension(&path) {
            continue;
        }
        let relative = path
            .strip_prefix(root)
            .map_err(|error| error.to_string())?
            .to_string_lossy()
            .replace('\\', "/");
        records.push(FileRecord {
            path: relative,
            name,
            kind: "file".into(),
            size: entry.metadata().map_err(|error| error.to_string())?.len(),
        });
    }
    Ok(())
}

fn seed_workspace(app: &AppHandle, destination: &Path) -> Result<(), String> {
    if destination.exists() {
        return Ok(());
    }
    fs::create_dir_all(destination).map_err(|error| error.to_string())?;
    let resource = app
        .path()
        .resource_dir()
        .map_err(|error| error.to_string())?
        .join("workspace/starter-site");
    let source = if resource.is_dir() {
        resource
    } else {
        PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../workspace/starter-site")
    };
    if !source.is_dir() {
        return Ok(());
    }
    for entry in fs::read_dir(source).map_err(|error| error.to_string())? {
        let entry = entry.map_err(|error| error.to_string())?;
        let target = destination.join(entry.file_name());
        if entry.path().is_file() {
            fs::copy(entry.path(), target).map_err(|error| error.to_string())?;
        }
    }
    Ok(())
}

#[tauri::command]
fn workspace_list(state: State<'_, WorkspaceState>) -> Result<Vec<FileRecord>, String> {
    let root = state
        .0
        .lock()
        .map_err(|_| "Workspace lock is unavailable.")?
        .clone();
    fs::create_dir_all(&root).map_err(|error| error.to_string())?;
    let mut records = Vec::new();
    collect_files(&root, &root, &mut records)?;
    records.sort_by(|left, right| {
        left.path
            .to_ascii_lowercase()
            .cmp(&right.path.to_ascii_lowercase())
    });
    Ok(records)
}

#[tauri::command]
fn workspace_info(state: State<'_, WorkspaceState>) -> Result<WorkspaceInfo, String> {
    let root = state
        .0
        .lock()
        .map_err(|_| "Workspace lock is unavailable.")?
        .clone();
    Ok(WorkspaceInfo {
        root: root.to_string_lossy().to_string(),
        name: root
            .file_name()
            .and_then(|value| value.to_str())
            .unwrap_or("workspace")
            .to_string(),
    })
}

#[tauri::command]
fn workspace_read(path: String, state: State<'_, WorkspaceState>) -> Result<String, String> {
    let root = state
        .0
        .lock()
        .map_err(|_| "Workspace lock is unavailable.")?
        .clone();
    let file = relative_path(&root, &path)?;
    if !file.is_file() || !allowed_extension(&file) {
        return Err("Only existing text workspace files can be opened.".into());
    }
    if fs::metadata(&file)
        .map_err(|error| error.to_string())?
        .len()
        > MAX_FILE_BYTES
    {
        return Err("This file is larger than the 512 KB editor limit.".into());
    }
    fs::read_to_string(file).map_err(|error| error.to_string())
}

#[tauri::command]
fn workspace_write(
    path: String,
    content: String,
    state: State<'_, WorkspaceState>,
) -> Result<(), String> {
    let root = state
        .0
        .lock()
        .map_err(|_| "Workspace lock is unavailable.")?
        .clone();
    let file = relative_path(&root, &path)?;
    if !allowed_extension(&file) {
        return Err("This file type is not enabled in the workspace editor.".into());
    }
    if content.as_bytes().len() as u64 > MAX_FILE_BYTES {
        return Err("This file is larger than the 512 KB editor limit.".into());
    }
    if let Some(parent) = file.parent() {
        fs::create_dir_all(parent).map_err(|error| error.to_string())?;
    }
    fs::write(file, content).map_err(|error| error.to_string())
}

#[tauri::command]
fn workspace_create_folder(
    path: String,
    state: State<'_, WorkspaceState>,
) -> Result<String, String> {
    let root = state
        .0
        .lock()
        .map_err(|_| "Workspace lock is unavailable.")?
        .clone();
    let folder = relative_path(&root, &path)?;
    if folder.exists() {
        return Err("A file or folder already exists at that path.".into());
    }
    fs::create_dir_all(&folder).map_err(|error| error.to_string())?;
    Ok(folder
        .strip_prefix(&root)
        .map_err(|error| error.to_string())?
        .to_string_lossy()
        .replace('\\', "/"))
}

#[tauri::command]
fn workspace_rename(
    path: String,
    name: String,
    state: State<'_, WorkspaceState>,
) -> Result<String, String> {
    let root = state
        .0
        .lock()
        .map_err(|_| "Workspace lock is unavailable.")?
        .clone();
    let source = relative_path(&root, &path)?;
    if !source.exists() || source == root {
        return Err("The workspace item does not exist.".into());
    }
    let destination = source
        .parent()
        .ok_or_else(|| "The workspace item has no parent folder.".to_string())?
        .join(safe_entry_name(&name)?);
    if destination.exists() {
        return Err("An item with that name already exists.".into());
    }
    fs::rename(&source, &destination).map_err(|error| error.to_string())?;
    Ok(destination
        .strip_prefix(&root)
        .map_err(|error| error.to_string())?
        .to_string_lossy()
        .replace('\\', "/"))
}

#[tauri::command]
fn workspace_delete(path: String, state: State<'_, WorkspaceState>) -> Result<(), String> {
    let root = state
        .0
        .lock()
        .map_err(|_| "Workspace lock is unavailable.")?
        .clone();
    let target = relative_path(&root, &path)?;
    if !target.exists() || target == root {
        return Err("The workspace item does not exist.".into());
    }
    if target.is_dir() {
        fs::remove_dir_all(target).map_err(|error| error.to_string())
    } else {
        fs::remove_file(target).map_err(|error| error.to_string())
    }
}

#[tauri::command]
fn workspace_create_project(
    name: String,
    template: String,
    state: State<'_, WorkspaceState>,
) -> Result<String, String> {
    let current = state
        .0
        .lock()
        .map_err(|_| "Workspace lock is unavailable.")?
        .clone();
    let parent = current
        .parent()
        .ok_or_else(|| "The current workspace has no parent folder.".to_string())?;
    let destination = parent.join(safe_entry_name(&name)?);
    if destination.exists() {
        return Err("A project with that name already exists.".into());
    }
    let files = match template.as_str() {
        "blank" => vec![("index.html", "<!doctype html>\n<html lang=\"en\"><head><meta charset=\"UTF-8\"><meta name=\"viewport\" content=\"width=device-width, initial-scale=1\"><title>My website</title></head><body><h1>Hello, web!</h1></body></html>\n")],
        "playground" => vec![
            ("index.html", "<!doctype html>\n<html lang=\"en\"><head><meta charset=\"UTF-8\"><meta name=\"viewport\" content=\"width=device-width, initial-scale=1\"><title>Playground</title><link rel=\"stylesheet\" href=\"styles.css\"></head><body><main><h1 id=\"title\">Try an idea</h1><button id=\"change\">Change the title</button></main><script src=\"app.js\"></script></body></html>\n"),
            ("styles.css", "body { margin: 0; min-height: 100vh; display: grid; place-items: center; font: 1rem system-ui; } main { text-align: center; }\n"),
            ("app.js", "document.querySelector('#change').addEventListener('click', () => { document.querySelector('#title').textContent = 'You changed the page!'; });\n"),
        ],
        _ => vec![
            ("index.html", "<!doctype html>\n<html lang=\"en\"><head><meta charset=\"UTF-8\"><meta name=\"viewport\" content=\"width=device-width, initial-scale=1\"><title>My first website</title><link rel=\"stylesheet\" href=\"styles.css\"></head><body><main class=\"site\"><p class=\"eyebrow\">MADE IN HTML STUDIO</p><h1>A small idea can become a website.</h1><p>Change this page, then press Run.</p><button id=\"hello\">Say hello</button><output id=\"message\"></output></main><script src=\"app.js\"></script></body></html>\n"),
            ("styles.css", ":root { font-family: system-ui, sans-serif; color: #e7eefb; background: #101a2b; } body { min-height: 100vh; margin: 0; display: grid; place-items: center; } .site { width: min(42rem, calc(100% - 3rem)); padding: 3rem; border: 1px solid #2d466d; border-radius: 1rem; background: #17243a; } button { padding: .7rem 1rem; cursor: pointer; }\n"),
            ("app.js", "document.querySelector('#hello')?.addEventListener('click', () => { document.querySelector('#message').textContent = 'It works!'; });\n"),
        ],
    };
    fs::create_dir_all(&destination).map_err(|error| error.to_string())?;
    for (relative, content) in files {
        fs::write(destination.join(relative), content).map_err(|error| error.to_string())?;
    }
    *state
        .0
        .lock()
        .map_err(|_| "Workspace lock is unavailable.")? = destination.clone();
    Ok(destination.to_string_lossy().to_string())
}

#[tauri::command]
fn workspace_set_root(path: String, state: State<'_, WorkspaceState>) -> Result<String, String> {
    let root = PathBuf::from(path)
        .canonicalize()
        .map_err(|error| error.to_string())?;
    if !root.is_dir() {
        return Err("The selected workspace is not a folder.".into());
    }
    *state
        .0
        .lock()
        .map_err(|_| "Workspace lock is unavailable.")? = root.clone();
    Ok(root.to_string_lossy().to_string())
}

#[tauri::command]
fn app_version() -> &'static str {
    "0.1.0"
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_shell::init())
        .manage(WorkspaceState(Mutex::new(PathBuf::from("."))))
        .invoke_handler(tauri::generate_handler![
            app_version,
            workspace_list,
            workspace_info,
            workspace_read,
            workspace_write,
            workspace_create_folder,
            workspace_rename,
            workspace_delete,
            workspace_create_project,
            workspace_set_root
        ])
        .setup(|app| {
            let app_data = app
                .path()
                .app_data_dir()?
                .join("workspace")
                .join("starter-site");
            seed_workspace(app.handle(), &app_data).map_err(std::io::Error::other)?;
            *app.state::<WorkspaceState>()
                .0
                .lock()
                .map_err(|_| std::io::Error::other("Workspace lock is unavailable."))? = app_data;
            if cfg!(debug_assertions) {
                app.handle()
                    .plugin(tauri_plugin_log::Builder::default().build())?;
            } else if let Ok((mut events, _child)) = app
                .shell()
                .sidecar("flaxon-api")
                .and_then(|command| command.env("VEL_STUDIO_PORT", "5180").spawn())
            {
                tauri::async_runtime::spawn(async move {
                    while let Some(event) = events.recv().await {
                        if let tauri_plugin_shell::process::CommandEvent::Error(error) = event {
                            eprintln!("Flaxon sidecar error: {error}");
                        }
                    }
                });
            }
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running HTML Studio");
}
