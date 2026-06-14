import { copyFileSync, existsSync, mkdirSync, readdirSync, rmSync, statSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const frontendRoot = resolve(here, "..");
const source = resolve(frontendRoot, "dist");
const target = resolve(frontendRoot, "..", "static");

if (!existsSync(source)) {
  throw new Error(`Build output does not exist: ${source}`);
}

rmSync(target, { recursive: true, force: true });
mkdirSync(target, { recursive: true });

function copyTree(from, to) {
  mkdirSync(to, { recursive: true });
  for (const entry of readdirSync(from)) {
    const sourcePath = resolve(from, entry);
    const targetPath = resolve(to, entry);
    if (statSync(sourcePath).isDirectory()) {
      copyTree(sourcePath, targetPath);
    } else {
      copyFileSync(sourcePath, targetPath);
    }
  }
}

copyTree(source, target);
console.log(`Copied React build to ${target}`);
