import { describe, it, expect } from "vitest";
// Import the functions under test — these will fail until fromPostgres.ts exists
import { extractMeta } from "../fromPostgres.js";
// Import meta.ts to verify the Graph API constant
import { GRAPH_API_VERSION } from "../meta.js";

// ---------------------------------------------------------------------------
// extractMeta() tests (per plan behavior spec)
// ---------------------------------------------------------------------------

describe("extractMeta", () => {
  it("returns {driveLink, landingPage} when metadata_json has drive_link", () => {
    const item = {
      id: 1,
      content_id: "ad-001",
      source: "ppspy",
      status: "ready_to_launch",
      creative_url: null,
      ad_copy: "Test ad",
      metadata_json: JSON.stringify({
        drive_link: "https://drive.google.com/file/d/abc123/view",
        landing_page: "https://newgarments.nl/sale",
      }),
    };

    const result = extractMeta(item);
    expect(result).not.toBeNull();
    expect(result?.driveLink).toBe("https://drive.google.com/file/d/abc123/view");
    expect(result?.landingPage).toBe("https://newgarments.nl/sale");
  });

  it("returns null when metadata_json has no drive_link", () => {
    const item = {
      id: 2,
      content_id: "ad-002",
      source: "ppspy",
      status: "ready_to_launch",
      creative_url: null,
      ad_copy: "Test ad",
      metadata_json: JSON.stringify({
        landing_page: "https://newgarments.nl/sale",
      }),
    };

    const result = extractMeta(item);
    expect(result).toBeNull();
  });

  it("defaults landingPage to https://newgarments.nl when absent from metadata_json", () => {
    const item = {
      id: 3,
      content_id: "ad-003",
      source: "ppspy",
      status: "ready_to_launch",
      creative_url: null,
      ad_copy: "Test ad",
      metadata_json: JSON.stringify({
        drive_link: "https://drive.google.com/file/d/xyz456/view",
      }),
    };

    const result = extractMeta(item);
    expect(result).not.toBeNull();
    expect(result?.landingPage).toBe("https://newgarments.nl");
  });

  it("returns null for invalid JSON in metadata_json", () => {
    const item = {
      id: 4,
      content_id: "ad-004",
      source: "ppspy",
      status: "ready_to_launch",
      creative_url: null,
      ad_copy: "Test ad",
      metadata_json: "not-valid-json{{",
    };

    const result = extractMeta(item);
    expect(result).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// Graph API version test
// ---------------------------------------------------------------------------

describe("meta.ts GRAPH_API version", () => {
  it("uses v23.0 (not expired v21.0)", () => {
    expect(GRAPH_API_VERSION).toBe("v23.0");
  });
});
