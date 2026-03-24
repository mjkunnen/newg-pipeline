/**
 * Google Apps Script for Pinterest Remake Pipeline
 * Deploy as Web App (Execute as: Me, Access: Anyone)
 *
 * Handles:
 * - action=add_remake: downloads fal.ai image to Drive, adds row to Sheet
 * - action=check_pin: checks if a pin_id already exists in the Sheet
 *
 * Sheet ID: 1BQ54wjilxW3F8rQFnVjwCRJtBTPDrSj3U5D0XYHjsgY
 * Drive folder: 1crvIaZtrMmuXslneAkX_q4rgcb1J5-FU
 */

var SHEET_ID = "1BQ54wjilxW3F8rQFnVjwCRJtBTPDrSj3U5D0XYHjsgY";
var SHEET_NAME = "Blad1";
var DRIVE_FOLDER_ID = "1crvIaZtrMmuXslneAkX_q4rgcb1J5-FU";

function doPost(e) {
  try {
    var params = e.parameter;
    var action = params.action;

    if (action === "add_remake") {
      return handleAddRemake(params);
    } else if (action === "check_pin") {
      return handleCheckPin(params);
    } else {
      return jsonResponse({ error: "Unknown action: " + action }, 400);
    }
  } catch (err) {
    return jsonResponse({ error: err.toString() }, 500);
  }
}

function handleAddRemake(params) {
  var pinId = params.pin_id;
  var pinUrl = params.pin_url;
  var outfitCombo = params.outfit_combo;
  var status = params.status || "done";
  var imageUrl = params.image_url; // fal.ai output URL
  var filename = params.filename;

  var driveFileId = "";
  var driveFilename = filename || ("remake_" + pinId + ".png");

  // Upload image to Drive if URL provided
  if (imageUrl && imageUrl !== "") {
    try {
      var folder = DriveApp.getFolderById(DRIVE_FOLDER_ID);

      // Create today's subfolder
      var today = Utilities.formatDate(new Date(), "Europe/Amsterdam", "yyyy-MM-dd");
      var subfolders = folder.getFoldersByName(today);
      var subfolder;
      if (subfolders.hasNext()) {
        subfolder = subfolders.next();
      } else {
        subfolder = folder.createFolder(today);
      }

      // Download and upload
      var response = UrlFetchApp.fetch(imageUrl, { muteHttpExceptions: true });
      if (response.getResponseCode() === 200) {
        var blob = response.getBlob().setName(driveFilename);
        var file = subfolder.createFile(blob);
        driveFileId = file.getId();
      }
    } catch (err) {
      // Continue without Drive upload on error
      driveFileId = "upload_failed: " + err.toString().substring(0, 100);
    }
  }

  // Add row to Sheet
  // Columns: A=drive_filename, B=drive_file_id, C=date_processed, D=status, E=outfit_combo, F=pin_url, G=pin_id
  var sheet = SpreadsheetApp.openById(SHEET_ID).getSheetByName(SHEET_NAME);
  var dateProcessed = Utilities.formatDate(new Date(), "Europe/Amsterdam", "yyyy-MM-dd HH:mm");

  sheet.appendRow([
    driveFilename,   // A
    driveFileId,     // B
    dateProcessed,   // C
    status,          // D
    outfitCombo,     // E
    pinUrl,          // F
    pinId            // G
  ]);

  return jsonResponse({
    success: true,
    pin_id: pinId,
    drive_file_id: driveFileId,
    drive_filename: driveFilename
  });
}

function handleCheckPin(params) {
  var pinId = params.pin_id;
  var sheet = SpreadsheetApp.openById(SHEET_ID).getSheetByName(SHEET_NAME);
  var colG = sheet.getRange("G:G").getValues();

  for (var i = 0; i < colG.length; i++) {
    if (colG[i][0] == pinId) {
      return jsonResponse({ exists: true, pin_id: pinId });
    }
  }

  return jsonResponse({ exists: false, pin_id: pinId });
}

function jsonResponse(data, code) {
  return ContentService
    .createTextOutput(JSON.stringify(data))
    .setMimeType(ContentService.MimeType.JSON);
}
