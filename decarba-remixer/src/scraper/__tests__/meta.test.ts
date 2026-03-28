import { describe, it, expect } from "vitest";
import { transformMetaResults } from "../meta.js";

describe("transformMetaResults", () => {
  it("skips items without adArchiveID", () => {
    const result = transformMetaResults([
      { adArchiveID: "", snapshot: { images: [{ original_image_url: "http://x.com/img.jpg" }] } } as any,
    ]);
    expect(result).toHaveLength(0);
  });

  it("skips items without any creative URL", () => {
    const result = transformMetaResults([
      { adArchiveID: "123", snapshot: { images: [], videos: [] } } as any,
    ]);
    expect(result).toHaveLength(0);
  });

  it("returns image type for image-only ads", () => {
    const result = transformMetaResults([
      { adArchiveID: "456", snapshot: { images: [{ original_image_url: "http://img.jpg" }] } } as any,
    ]);
    expect(result).toHaveLength(1);
    expect(result[0].id).toBe("meta_456");
    expect(result[0].type).toBe("image");
    expect(result[0].creativeUrl).toBe("http://img.jpg");
  });

  it("returns video type when video URL present", () => {
    const result = transformMetaResults([
      {
        adArchiveID: "789",
        snapshot: {
          images: [{ original_image_url: "http://thumb.jpg" }],
          videos: [{ video_hd_url: "http://vid.mp4", video_preview_image_url: "http://preview.jpg" }],
        },
      } as any,
    ]);
    expect(result).toHaveLength(1);
    expect(result[0].type).toBe("video");
    expect(result[0].creativeUrl).toBe("http://vid.mp4");
    expect(result[0].thumbnailUrl).toBe("http://preview.jpg");
  });

  it("prefixes content_id with meta_", () => {
    const result = transformMetaResults([
      { adArchiveID: "ABC123", snapshot: { images: [{ original_image_url: "http://img.jpg" }] } } as any,
    ]);
    expect(result[0].id).toBe("meta_ABC123");
  });
});
