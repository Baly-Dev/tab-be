#!/usr/bin/env node
"use strict";

const { execFile } = require("child_process");
const path = require("path");

const chrome = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const pdfPath = path.join(__dirname, "FlashTable-BMC.pdf");
const page = "http://127.0.0.1:8765/report/flashtable-bmc.html";

function printPdf() {
  return new Promise(function (resolve, reject) {
    execFile(chrome, [
      "--headless",
      "--disable-gpu",
      "--no-pdf-header-footer",
      "--virtual-time-budget=12000",
      "--print-to-pdf=" + pdfPath,
      page
    ], { timeout: 30000 }, function (err) {
      if (err) reject(err);
      else resolve(pdfPath);
    });
  });
}

if (require.main === module) {
  printPdf().then(function (file) {
    console.log(file);
  }).catch(function (err) {
    console.error(err);
    process.exit(1);
  });
}

module.exports = { printPdf, pdfPath };
