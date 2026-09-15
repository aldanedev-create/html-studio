import { cp, mkdir, rm } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const source = resolve(root, "node_modules/monaco-editor/min/vs");
const destination = resolve(root, "static/vendor/monaco/vs");

try {
  await mkdir(dirname(destination), { recursive: true });
  await rm(destination, { recursive: true, force: true });
  await cp(source, destination, { recursive: true });
  console.log(`Vendored Monaco from ${source}`);
} catch (error) {
  console.error("Could not vendor Monaco. Run npm install first.", error.message);
  process.exitCode = 1;
}
