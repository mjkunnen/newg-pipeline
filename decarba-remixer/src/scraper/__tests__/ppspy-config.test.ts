import { describe, it, expect } from "vitest";
import { loadConfig } from "../config.js";

describe("PPSpy config loading", () => {
  it("reads search_terms from ppspy-settings.json", () => {
    const config = loadConfig<{ search_terms: string[] }>("ppspy-settings.json");
    expect(config.search_terms).toContain("decarba");
    expect(Array.isArray(config.search_terms)).toBe(true);
  });
});
