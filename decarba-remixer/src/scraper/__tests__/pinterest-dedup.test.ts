import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { writeToContentAPI } from "../contentApi.js";

describe("Pinterest dedup via Postgres", () => {
  const originalEnv = process.env;

  beforeEach(() => {
    process.env = { ...originalEnv };
    delete process.env.CONTENT_API_URL;
    delete process.env.DASHBOARD_SECRET;
  });

  afterEach(() => {
    process.env = originalEnv;
  });

  it("writeToContentAPI returns {written:0, skipped:0} when CONTENT_API_URL not set", async () => {
    const result = await writeToContentAPI([{
      id: "pinterest_123", type: "image", creativeUrl: "http://x.com/img.jpg",
      reach: 0, daysActive: 0, startedAt: "2026-01-01",
      platforms: ["pinterest"], scrapedAt: "2026-01-01T00:00:00Z",
    }], "pinterest");
    expect(result).toEqual({ written: 0, skipped: 0 });
  });

  it("writeToContentAPI returns {written:0, skipped:0} when DASHBOARD_SECRET not set", async () => {
    process.env.CONTENT_API_URL = "http://localhost:8000";
    const result = await writeToContentAPI([{
      id: "pinterest_456", type: "image", creativeUrl: "http://x.com/img2.jpg",
      reach: 0, daysActive: 0, startedAt: "2026-01-01",
      platforms: ["pinterest"], scrapedAt: "2026-01-01T00:00:00Z",
    }], "pinterest");
    expect(result).toEqual({ written: 0, skipped: 0 });
  });

  it("writeToContentAPI returns {written:0, skipped:0} for empty ads array", async () => {
    const result = await writeToContentAPI([], "pinterest");
    expect(result).toEqual({ written: 0, skipped: 0 });
  });
});
