// Test: Oxylabs + DOM parsing for TikTok posts
require("dotenv").config({ path: require("path").join(__dirname, "..", "decarba-remixer", ".env") });
require("dotenv").config({ path: require("path").join(__dirname, "..", ".env") });

const OXYLABS_USER = process.env.OXYLABS_USERNAME;
const OXYLABS_PASS = process.env.OXYLABS_PASSWORD;
const USERNAME = "strhvn2";

async function main() {
  console.log("Testing Oxylabs for TikTok @" + USERNAME + "...");

  const payload = {
    source: "universal",
    url: "https://www.tiktok.com/@" + USERNAME,
    render: "html",
    browser_instructions: [
      { type: "wait", wait_time_s: 5 },
      { type: "scroll", x: 0, y: 2000, wait_time_s: 2 },
    ],
  };

  const resp = await fetch("https://realtime.oxylabs.io/v1/queries", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: "Basic " + Buffer.from(OXYLABS_USER + ":" + OXYLABS_PASS).toString("base64"),
    },
    body: JSON.stringify(payload),
  });

  if (!resp.ok) {
    console.log("Error:", resp.status, (await resp.text()).substring(0, 300));
    return;
  }

  const result = await resp.json();
  const content = result.results?.[0]?.content || "";
  console.log("Content:", content.length, "chars");

  // Parse DOM: TikTok renders post links as <a> with href like /@username/video/ID or /@username/photo/ID
  var postLinks = [];
  var linkRegex = /href="https:\/\/www\.tiktok\.com\/@[^"]*?\/(video|photo)\/(\d+)"/g;
  var m;
  while ((m = linkRegex.exec(content)) !== null) {
    postLinks.push({ type: m[1], id: m[2] });
  }

  // Deduplicate
  var seen = new Set();
  postLinks = postLinks.filter(function(p) {
    if (seen.has(p.id)) return false;
    seen.add(p.id);
    return true;
  });

  console.log("Unique posts found:", postLinks.length);
  var photos = postLinks.filter(function(p) { return p.type === "photo"; });
  var videos = postLinks.filter(function(p) { return p.type === "video"; });
  console.log("  Photos (carousels):", photos.length);
  console.log("  Videos:", videos.length);

  for (var p of postLinks.slice(0, 10)) {
    console.log("  " + p.type + " " + p.id);
  }

  // For carousel posts, we can fetch individual post data
  // TikTok's oembed endpoint is public and doesn't need auth
  if (photos.length > 0) {
    console.log("\n--- Testing oembed for carousel post ---");
    var testId = photos[0].id;
    var oembedUrl = "https://www.tiktok.com/oembed?url=https://www.tiktok.com/@" + USERNAME + "/photo/" + testId;
    try {
      var oResp = await fetch(oembedUrl);
      if (oResp.ok) {
        var oData = await oResp.json();
        console.log("Oembed works! Title:", (oData.title || "").substring(0, 60));
        console.log("Author:", oData.author_name);
        // oembed doesn't have slide images, but confirms post exists
      } else {
        console.log("Oembed status:", oResp.status);
      }
    } catch(e) {
      console.log("Oembed error:", e.message);
    }
  }

  // Check if we can get SecUid for API calls
  var idx = content.indexOf("__UNIVERSAL_DATA_FOR_REHYDRATION__");
  if (idx !== -1) {
    var eqIdx = content.indexOf("=", idx);
    var startIdx = content.indexOf("{", eqIdx);
    if (startIdx !== -1) {
      var depth = 0, endIdx = -1;
      for (var i = startIdx; i < content.length; i++) {
        if (content[i] === "{") depth++;
        else if (content[i] === "}") { depth--; if (depth === 0) { endIdx = i; break; } }
      }
      if (endIdx !== -1) {
        var data = JSON.parse(content.substring(startIdx, endIdx + 1));
        var scope = data["__DEFAULT_SCOPE__"] || {};
        var userDetail = scope["webapp.user-detail"] || {};
        var secUid = userDetail.userInfo?.user?.secUid;
        if (secUid) {
          console.log("\nSecUid found:", secUid.substring(0, 30) + "...");
          console.log("Can use this for API pagination calls");
        }
      }
    }
  }

  // Look for any view count data in the page (aria-labels, data attributes)
  var viewCounts = [];
  var viewRegex = /(\d+(?:\.\d+)?[KMB]?)\s*(?:views|plays)/gi;
  var vm;
  while ((vm = viewRegex.exec(content)) !== null) {
    viewCounts.push(vm[1]);
  }
  if (viewCounts.length > 0) {
    console.log("\nView counts found in DOM:", viewCounts.slice(0, 10));
  }

  // Check for aria-label with view counts
  var ariaRegex = /aria-label="[^"]*?(\d[\d.]*[KMB]?)\s*views[^"]*"/gi;
  var ariaMatches = [];
  while ((vm = ariaRegex.exec(content)) !== null) {
    ariaMatches.push(vm[0].substring(0, 80));
  }
  if (ariaMatches.length > 0) {
    console.log("Aria labels with views:", ariaMatches.slice(0, 5));
  }
}

main().catch(console.error);
