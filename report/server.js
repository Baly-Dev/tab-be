#!/usr/bin/env node
"use strict";

const http = require("http");
const fs = require("fs");
const path = require("path");
const { printPdf, pdfPath } = require("./build");

const root = path.join(__dirname, "..");
const types = {
  ".html": "text/html; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".md": "text/markdown; charset=utf-8",
  ".pdf": "application/pdf",
  ".svg": "image/svg+xml",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".webp": "image/webp"
};

let printing = null;

function generate() {
  if (!printing) {
    printing = printPdf().finally(function () {
      printing = null;
    });
  }
  return printing;
}

function sendFile(res, file) {
  fs.readFile(file, function (err, data) {
    if (err) {
      res.writeHead(404);
      res.end();
      return;
    }
    res.writeHead(200, {
      "Content-Type": types[path.extname(file)] || "application/octet-stream",
      "Cache-Control": "no-store"
    });
    res.end(data);
  });
}

const server = http.createServer(function (req, res) {
  const url = new URL(req.url, "http://127.0.0.1:8765");
  if (url.pathname === "/report/pdf") {
    generate().then(function () {
      const data = fs.readFileSync(pdfPath);
      res.writeHead(200, {
        "Content-Type": "application/pdf",
        "Content-Length": data.length,
        "Cache-Control": "no-store"
      });
      res.end(data);
    }).catch(function () {
      res.writeHead(500, { "Content-Type": "text/plain; charset=utf-8" });
      res.end("Non riesco a generare il PDF.");
    });
    return;
  }

  let pathname = decodeURIComponent(url.pathname);
  if (pathname.endsWith("/")) pathname += "index.html";
  const file = path.normalize(path.join(root, pathname));
  if (!file.startsWith(root)) {
    res.writeHead(403);
    res.end();
    return;
  }
  sendFile(res, file);
});

server.listen(8765, "127.0.0.1");
