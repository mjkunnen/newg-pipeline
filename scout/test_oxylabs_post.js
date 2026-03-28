// Test: Fetch TikTok carousel post - check all available data
require("dotenv").config({ path: require("path").join(__dirname, "..", "decarba-remixer", ".env") });
require("dotenv").config({ path: require("path").join(__dirname, "..", ".env") });

const OXYLABS_USER = process.env.OXYLABS_USERNAME;
const OXYLABS_PASS = process.env.OXYLABS_PASSWORD;
const POST_URL = "https://www.tiktok.com/@strhvn2/photo/7620837369402461462";

async function fetchOxylabs(url, render) {
  var payload = { source: "universal", url: url };
  if (render) payload.render = "html";

  var resp = await fetch("https://realtime.oxylabs.io/v1/queries", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: "Basic " + Buffer.from(OXYLABS_USER + ":" + OXYLABS_PASS).toString("base64"),
    },
    body: JSON.stringify(payload),
  });

  var result = await resp.json();
  return result.results?.[0]?.content || "";
}

function extractUniversalData(content) {
  var idx = content.indexOf("__UNIVERSAL_DATA_FOR_REHYDRATION__");
  if (idx === -1) return null;
  var eqIdx = content.indexOf("=", idx);
  var startIdx = content.indexOf("{", eqIdx);
  if (startIdx === -1) return null;
  var depth = 0, endIdx = -1;
  for (var i = startIdx; i < content.length; i++) {
    if (content[i] === "{") depth++;
    else if (content[i] === "}") { depth--; if (depth === 0) { endIdx = i; break; } }
  }
  if (endIdx === -1) return null;
  return JSON.parse(content.substring(startIdx, endIdx + 1));
}

async function main() {
  // Try with render
  console.log("Fetching with render:", POST_URL);
  var content = await fetchOxylabs(POST_URL, true);
  console.log("Content:", content.length, "chars");

  var data = extractUniversalData(content);
  if (!data) {
    console.log("No UNIVERSAL_DATA found");
    return;
  }

  var scope = data["__DEFAULT_SCOPE__"] || {};
  console.log("All scope keys:", Object.keys(scope));

  // Dump all scope values that contain post-like data
  for (var key of Object.keys(scope)) {
    var val = scope[key];
    var str = JSON.stringify(val);
    if (str.includes("playCount") || str.includes("imagePost") || str.includes("7620837")) {
      console.log("\nKey '" + key + "' contains post data!");
      console.log("  Size:", str.length);
      // Try to find the post
      if (val.itemInfo) {
        console.log("  Has itemInfo!");
        var item = val.itemInfo.itemStruct || {};
        console.log("  ID:", item.id, "Views:", item.stats?.playCount);
      }
      if (val.itemStruct) {
        console.log("  Has itemStruct directly!");
      }
      // Show first level keys
      console.log("  Keys:", Object.keys(val));
    }
  }

  // Also search the full JSON for imagePost
  var fullStr = JSON.stringify(data);
  if (fullStr.includes("imagePost")) {
    console.log("\nimagePost found in data! Searching...");
    var imgIdx = fullStr.indexOf('"imagePost"');
    console.log("Context:", fullStr.substring(Math.max(0, imgIdx - 50), imgIdx + 200));
  }

  // Check for SIGI_STATE or other data formats
  if (content.includes("SIGI_STATE")) {
    console.log("\nSIGI_STATE found!");
  }

  // Look for JSON-LD
  var ldMatch = content.match(/<script type="application\/ld\+json">([\s\S]*?)<\/script>/);
  if (ldMatch) {
    try {
      var ld = JSON.parse(ldMatch[1]);
      console.log("\nJSON-LD found!");
      console.log("  Type:", ld["@type"]);
      console.log("  Name:", ld.name);
      console.log("  Description:", (ld.description || "").substring(0, 80));
      if (ld.interactionStatistic) {
        for (var stat of ld.interactionStatistic) {
          console.log("  " + stat.interactionType?.replace("http://schema.org/", "") + ":", stat.userInteractionCount);
        }
      }
    } catch(e) {}
  }

  // Check meta tags for view counts
  var metaMatch = content.match(/property="og:description"[^>]*content="([^"]*)"/);
  if (metaMatch) {
    console.log("\nOG description:", metaMatch[1].substring(0, 120));
  }
}

main().catch(console.error);
