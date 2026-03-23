import { readFile } from "fs/promises";
import { basename } from "path";

export async function uploadToGoogleDrive(
  files: string[],
  folderName?: string
): Promise<string[]> {
  const folderId = process.env.GOOGLE_DRIVE_FOLDER_ID;
  if (!folderId) {
    console.log("[drive] GOOGLE_DRIVE_FOLDER_ID not set, skipping upload");
    return [];
  }

  // TODO: Implement with googleapis package or Zapier webhook
  // Option 1: googleapis with service account
  //   - GOOGLE_SERVICE_ACCOUNT_KEY path in .env
  //   - Create subfolder, upload files
  // Option 2: Zapier webhook
  //   - POST file URLs to webhook endpoint

  const urls: string[] = [];
  for (const filePath of files) {
    const fileName = basename(filePath);
    const fileBuffer = await readFile(filePath);
    console.log(
      `[drive] Would upload ${fileName} (${(fileBuffer.length / 1024).toFixed(0)}KB) to ${folderName || folderId}`
    );
    urls.push(`https://drive.google.com/drive/folders/${folderId}`);
  }

  return urls;
}
