import { execSync } from "child_process";
import { join, basename } from "path";
import { writeFileSync, unlinkSync, mkdirSync, existsSync } from "fs";
import type { ScrapedAd, RemixResult } from "../scraper/types.js";

const OUTPUT_BASE = join(import.meta.dirname, "../../output/remixed");
const ASSETS_DIR = join(import.meta.dirname, "../../assets");

function todayDir(): string {
  return new Date().toISOString().split("T")[0];
}

function checkFfmpeg(): void {
  try {
    execSync("ffmpeg -version", { stdio: "pipe" });
  } catch {
    throw new Error("ffmpeg not found. Install it: https://ffmpeg.org/download.html");
  }
  try {
    execSync("ffprobe -version", { stdio: "pipe" });
  } catch {
    throw new Error("ffprobe not found. Install it with ffmpeg.");
  }
}

export function getVideoDuration(videoPath: string): number {
  const result = execSync(
    `ffprobe -v error -show_entries format=duration -of csv=p=0 "${videoPath}"`,
    { encoding: "utf-8" }
  );
  return parseFloat(result.trim());
}

function getVideoCodec(videoPath: string): string {
  const result = execSync(
    `ffprobe -v error -select_streams v:0 -show_entries stream=codec_name -of csv=p=0 "${videoPath}"`,
    { encoding: "utf-8" }
  );
  return result.trim();
}

export async function remixVideoAd(
  videoPath: string,
  trimSeconds: number = 2
): Promise<string> {
  checkFfmpeg();

  const outputDir = join(OUTPUT_BASE, todayDir());
  mkdirSync(outputDir, { recursive: true });

  const endcardPath = join(ASSETS_DIR, "endcard.mp4");
  const hasEndcard = existsSync(endcardPath);
  const name = basename(videoPath, ".mp4");
  const outputPath = join(outputDir, `remix_${name}.mp4`);

  // Get duration
  const duration = getVideoDuration(videoPath);
  console.log(`[video] Duration: ${duration}s`);

  // Decide trim
  const shouldTrim = duration > trimSeconds + 1;
  const trimTo = shouldTrim ? duration - trimSeconds : duration;

  if (shouldTrim) {
    console.log(`[video] Trimming last ${trimSeconds}s (to ${trimTo.toFixed(1)}s)`);
  } else {
    console.log(`[video] Video too short to trim, keeping full`);
  }

  const trimmedPath = join(outputDir, `_trimmed_${name}.mp4`);
  const concatListPath = join(outputDir, `_concat_${name}.txt`);

  try {
    if (!hasEndcard) {
      // No endcard — just trim
      if (shouldTrim) {
        const cmd = `ffmpeg -y -i "${videoPath}" -t ${trimTo} -c copy "${outputPath}"`;
        console.log(`[video] ${cmd}`);
        execSync(cmd, { stdio: "pipe" });
      } else {
        // Just copy
        execSync(`ffmpeg -y -i "${videoPath}" -c copy "${outputPath}"`, { stdio: "pipe" });
      }
      console.log(`[video] Output (no endcard): ${outputPath}`);
      return outputPath;
    }

    // Check codecs
    const inputCodec = getVideoCodec(videoPath);
    const endcardCodec = getVideoCodec(endcardPath);
    const codecsMatch = inputCodec === endcardCodec && inputCodec === "h264";

    if (codecsMatch && shouldTrim) {
      // Fast path: stream copy
      console.log(`[video] Codecs match (${inputCodec}), using stream copy`);

      execSync(`ffmpeg -y -i "${videoPath}" -t ${trimTo} -c copy "${trimmedPath}"`, { stdio: "pipe" });
      writeFileSync(concatListPath,
        `file '${trimmedPath.replace(/\\/g, "/")}'\nfile '${endcardPath.replace(/\\/g, "/")}'`
      );
      execSync(`ffmpeg -y -f concat -safe 0 -i "${concatListPath}" -c copy "${outputPath}"`, { stdio: "pipe" });
    } else {
      // Re-encode for compatibility
      console.log(`[video] Codecs differ (${inputCodec} vs ${endcardCodec}), re-encoding`);

      const reEncodedTrimmed = join(outputDir, `_enc_trimmed_${name}.mp4`);
      const reEncodedEndcard = join(outputDir, `_enc_endcard_${name}.mp4`);

      const trimFlag = shouldTrim ? `-t ${trimTo}` : "";
      execSync(
        `ffmpeg -y -i "${videoPath}" ${trimFlag} -c:v libx264 -c:a aac -r 30 -preset fast "${reEncodedTrimmed}"`,
        { stdio: "pipe" }
      );
      execSync(
        `ffmpeg -y -i "${endcardPath}" -c:v libx264 -c:a aac -r 30 -preset fast "${reEncodedEndcard}"`,
        { stdio: "pipe" }
      );

      writeFileSync(concatListPath,
        `file '${reEncodedTrimmed.replace(/\\/g, "/")}'\nfile '${reEncodedEndcard.replace(/\\/g, "/")}'`
      );
      execSync(`ffmpeg -y -f concat -safe 0 -i "${concatListPath}" -c copy "${outputPath}"`, { stdio: "pipe" });

      try { unlinkSync(reEncodedTrimmed); } catch {}
      try { unlinkSync(reEncodedEndcard); } catch {}
    }

    // Cleanup temp files
    try { unlinkSync(trimmedPath); } catch {}
    try { unlinkSync(concatListPath); } catch {}

    console.log(`[video] Output: ${outputPath}`);
    return outputPath;
  } catch (err) {
    try { unlinkSync(trimmedPath); } catch {}
    try { unlinkSync(concatListPath); } catch {}
    throw err;
  }
}
