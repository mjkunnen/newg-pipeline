import { describe, it, expect } from "vitest";
import { meetsEngagementThreshold } from "../tiktok.js";

describe("meetsEngagementThreshold", () => {
  it("returns true when play_count/follower_count equals threshold exactly", () => {
    expect(meetsEngagementThreshold(45000, 300000, 0.15)).toBe(true);
  });

  it("returns false when play_count/follower_count is below threshold", () => {
    expect(meetsEngagementThreshold(44999, 300000, 0.15)).toBe(false);
  });

  it("returns true when follower_count is 0 and play_count >= min_reach_fallback", () => {
    expect(meetsEngagementThreshold(5000, 0, 0.15, 3000)).toBe(true);
  });

  it("returns false when follower_count is 0 and play_count < min_reach_fallback", () => {
    expect(meetsEngagementThreshold(2000, 0, 0.15, 3000)).toBe(false);
  });
});
