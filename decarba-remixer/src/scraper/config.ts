import { readFileSync } from "fs";
import { join } from "path";

const CONFIG_DIR = join(import.meta.dirname, "../../config");

export function loadConfig<T>(filename: string): T {
  const path = join(CONFIG_DIR, filename);
  try {
    return JSON.parse(readFileSync(path, "utf-8")) as T;
  } catch (err) {
    throw new Error(`Failed to load config ${filename} from ${path}: ${err}`);
  }
}
