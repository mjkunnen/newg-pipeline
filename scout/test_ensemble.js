// Test EnsembleData - verify slideshow data + views + image URLs
const TOKEN = "VFmtMGxCtJPr7HZM";

async function main() {
  var url = "https://ensembledata.com/apis/tt/user/posts?username=strhvn2&depth=1&token=" + TOKEN;
  var resp = await fetch(url);
  var result = await resp.json();
  var posts = result.data || [];

  console.log("Posts:", posts.length, "| Cursor:", result.nextCursor);

  var slideshows = 0;
  for (var post of posts) {
    var isSlideshow = Boolean(post.image_post_info);
    if (isSlideshow) slideshows++;

    var stats = post.statistics || {};
    console.log("\n---");
    console.log("ID:", post.aweme_id);
    console.log("Views:", stats.play_count, "| Likes:", stats.digg_count, "| Shares:", stats.share_count);
    console.log("Date:", new Date(post.create_time * 1000).toISOString().split("T")[0]);
    console.log("Slideshow:", isSlideshow);
    console.log("Author:", post.author ? post.author.unique_id : "?");
    console.log("Desc:", (post.desc || "").substring(0, 60));

    if (post.image_post_info) {
      var images = post.image_post_info.images || [];
      console.log("  Slides:", images.length);
      if (images[0]) {
        // Check image URL structure
        var img = images[0];
        var imgUrl = img.display_image || img.owner_watermark_image || img.thumbnail || {};
        var urlList = imgUrl.url_list || [];
        console.log("  Image keys:", Object.keys(img).slice(0, 8));
        if (urlList.length > 0) {
          console.log("  URL:", urlList[0].substring(0, 120));
        } else {
          // Try other paths
          for (var key of Object.keys(img)) {
            var val = img[key];
            if (val && typeof val === "object" && val.url_list) {
              console.log("  Found URLs at:", key);
              console.log("  URL:", val.url_list[0].substring(0, 120));
              break;
            }
          }
        }
      }
    }
  }

  console.log("\n=== RESULT ===");
  console.log("Total:", posts.length, "| Slideshows:", slideshows);
  console.log("Cost: 1 unit (50/day free)");
}

main().catch(console.error);
