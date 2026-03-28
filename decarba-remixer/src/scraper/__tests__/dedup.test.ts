import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { writeToContentAPI } from "../contentApi.js";

describe("writeToContentAPI", () => {
  const originalEnv = process.env;

  beforeEach(() => {
    process.env = { ...originalEnv };
    delete process.env.CONTENT_API_URL;
    delete process.env.DASHBOARD_SECRET;
  });

  afterEach(() => {
    process.env = originalEnv;
  });

  it("returns {written:0, skipped:0} when CONTENT_API_URL not set", async () => {
    const result = await writeToContentAPI([{
      id: "test_1", type: "image", creativeUrl: "http://x.com/img.jpg",
      reach: 1000, daysActive: 1, startedAt: "2026-01-01",
      platforms: ["tiktok"], scrapedAt: "2026-01-01T00:00:00Z",
    }], "tiktok");
    expect(result).toEqual({ written: 0, skipped: 0 });
  });

  it("returns {written:0, skipped:0} when DASHBOARD_SECRET not set", async () => {
    process.env.CONTENT_API_URL = "http://localhost:8000";
    const result = await writeToContentAPI([{
      id: "test_2", type: "image", creativeUrl: "http://x.com/img.jpg",
      reach: 1000, daysActive: 1, startedAt: "2026-01-01",
      platforms: ["tiktok"], scrapedAt: "2026-01-01T00:00:00Z",
    }], "tiktok");
    expect(result).toEqual({ written: 0, skipped: 0 });
  });
});
