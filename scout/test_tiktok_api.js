// Test: can we scrape TikTok profile data directly via SSR?
const https = require("https");

const USERNAME = "strhvn2";
const URL = `https://www.tiktok.com/@${USERNAME}`;

const options = {
  headers: {
    "User-Agent":
      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    Accept:
      "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
  },
};

function fetch(url) {
  return new Promise((resolve, reject) => {
    https.get(url, options, (res) => {
      if (res.statusCode >= 300 && res.statusCode < 400 && res.headers.location) {
        return fetch(res.headers.location).then(resolve).catch(reject);
      }
      const chunks = [];
      res.on("data", (c) => chunks.push(c));
      res.on("end", () => resolve(Buffer.concat(chunks).toString()));
      res.on("error", reject);
    });
  });
}

async function main() {
  console.log("Fetching", URL);
  const html = await fetch(URL);
  console.log("HTML length:", html.length);

  // Extract __UNIVERSAL_DATA_FOR_REHYDRATION__
  const match = html.match(
    /__UNIVERSAL_DATA_FOR_REHYDRATION__\s*=\s*(\{.+?\})\s*<\/script>/s
  );
  if (!match) {
    console.log("No UNIVERSAL_DATA found");
    // Check if it's a challenge page
    if (html.includes("captcha") || html.includes("verify")) {
      console.log("CAPTCHA/verification page detected");
    }
    return;
  }

  const data = JSON.parse(match[1]);
  const defaultScope = data["__DEFAULT_SCOPE__"] || {};
  console.log("Scope keys:", Object.keys(defaultScope));

  // User info
  const userDetail = defaultScope["webapp.user-detail"] || {};
  const userInfo = userDetail.userInfo || {};
  console.log("\nUser:", userInfo.user?.uniqueId);
  console.log("SecUid:", (userInfo.user?.secUid || "").substring(0, 40) + "...");
  console.log("Followers:", userInfo.stats?.followerCount);

  // Item list (posts shown on profile SSR)
  const itemList = userDetail.itemList || defaultScope["webapp.user-post"]?.itemList || [];
  console.log("\nPosts in SSR:", itemList.length);

  if (itemList.length > 0) {
    for (const item of itemList.slice(0, 5)) {
      const isSlideshow = !!(item.imagePost || item.imagePostInfo);
      console.log("\n---");
      console.log("ID:", item.id);
      console.log("Desc:", (item.desc || "").substring(0, 60));
      console.log("Play count:", item.stats?.playCount);
      console.log("Create time:", item.createTime, new Date(item.createTime * 1000).toISOString().split("T")[0]);
      console.log("Is slideshow:", isSlideshow);

      if (item.imagePost) {
        const images = item.imagePost.images || [];
        console.log("Slideshow images:", images.length);
        if (images.length > 0) {
          const urls = images.map(
            (img) => img.imageURL?.urlList?.[0] || "no-url"
          );
          console.log("First image URL:", urls[0]?.substring(0, 80));
        }
      }
      if (item.imagePostInfo) {
        console.log("imagePostInfo keys:", Object.keys(item.imagePostInfo));
        const images = item.imagePostInfo.images || [];
        console.log("Images count:", images.length);
      }
    }
  }
}

main().catch(console.error);
