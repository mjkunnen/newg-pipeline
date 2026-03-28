import { writeFile, mkdir } from "fs/promises";
import { join } from "path";

/**
 * Download a Google Drive creative to a local tmp directory.
 * Converts share links to direct download URLs.
 * Throws if the response is an HTML page (Drive confirmation page).
 *
 * @param driveLink  Google Drive share link (e.g. https://drive.google.com/file/d/ID/view)
 * @param adId       Ad identifier — used for the output filename
 * @param tmpDir     Directory to write the downloaded file into
 * @returns          Absolute path of the downloaded file
 */
export async function downloadCreative(
  driveLink: string,
  adId: string,
  tmpDir: string,
): Promise<string> {
  await mkdir(tmpDir, { recursive: true });

  // Convert Drive share link to direct download
  let downloadUrl = driveLink;
  const fileIdMatch = driveLink.match(/\/d\/([a-zA-Z0-9_-]+)/);
  if (fileIdMatch) {
    // confirm=t bypasses the "virus scan" confirmation page for larger files
    downloadUrl = `https://drive.google.com/uc?export=download&confirm=t&id=${fileIdMatch[1]}`;
  }

  console.log(`[driveDownload] Downloading creative for ${adId}...`);
  const resp = await fetch(downloadUrl, { redirect: "follow" });
  if (!resp.ok) {
    throw new Error(`Download failed: ${resp.status} ${downloadUrl}`);
  }

  const contentType = resp.headers.get("content-type") || "";
  let ext = ".jpg";
  if (contentType.includes("video") || contentType.includes("mp4")) ext = ".mp4";
  else if (contentType.includes("png")) ext = ".png";
  else if (contentType.includes("webp")) ext = ".webp";

  const buffer = Buffer.from(await resp.arrayBuffer());

  // Verify we got actual media, not an HTML confirmation page
  const head = buffer.subarray(0, 20).toString("utf8");
  if (head.includes("<!DOCTYPE") || head.includes("<html")) {
    throw new Error(
      `Download returned HTML page instead of media file — is the Drive file shared publicly?`,
    );
  }

  const filePath = join(tmpDir, `${adId}${ext}`);
  await writeFile(filePath, buffer);
  console.log(
    `[driveDownload] Downloaded: ${filePath} (${(buffer.length / 1024).toFixed(0)}KB)`,
  );
  return filePath;
}
