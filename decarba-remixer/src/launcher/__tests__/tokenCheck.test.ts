import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { checkTokenType } from "../fromPostgres.js";

// ---------------------------------------------------------------------------
// checkTokenType() tests — token heuristic (personal vs system user)
// ---------------------------------------------------------------------------

describe("checkTokenType", () => {
  let warnSpy: ReturnType<typeof vi.spyOn>;
  let logSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    warnSpy = vi.spyOn(console, "warn").mockImplementation(() => {});
    logSpy = vi.spyOn(console, "log").mockImplementation(() => {});
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("logs warning when name looks like a human name (personal token)", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ name: "Max Kunnen", id: "12345" }),
    }));

    await checkTokenType("fake-token");

    expect(warnSpy).toHaveBeenCalledWith(
      expect.stringContaining("personal token"),
    );
  });

  it("logs confirmation when name matches system user pattern", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ name: "System User", id: "67890" }),
    }));

    await checkTokenType("fake-token");

    expect(logSpy).toHaveBeenCalledWith(
      expect.stringContaining("confirmed"),
    );
  });

  it("logs confirmation for bot-style name", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ name: "NEWG Bot", id: "99999" }),
    }));

    await checkTokenType("fake-token");

    expect(logSpy).toHaveBeenCalledWith(
      expect.stringContaining("confirmed"),
    );
  });

  it("handles fetch failure gracefully (no throw)", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("Network error")));

    // Should not throw
    await expect(checkTokenType("fake-token")).resolves.toBeUndefined();

    expect(warnSpy).toHaveBeenCalledWith(
      expect.stringContaining("Token type check failed"),
      expect.stringContaining("Network error"),
    );
  });

  it("handles non-ok response gracefully (no throw)", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: false,
      status: 401,
    }));

    await expect(checkTokenType("bad-token")).resolves.toBeUndefined();

    expect(warnSpy).toHaveBeenCalledWith(
      expect.stringContaining("Could not verify token type"),
      401,
    );
  });
});
