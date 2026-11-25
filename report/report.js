(function () {
  var SOURCE = "../BUSINESS_MODEL.md";
  var report = document.getElementById("report");
  var status = document.getElementById("status");
  var button = document.getElementById("genera");

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  function inline(s) {
    var t = escapeHtml(s).replace(/\u00a0/g, " ");
    t = t.replace(/\+\+\*\*([\s\S]+?)\+\+\s*-\*\*/g, "<strong><span class=\"ul\">$1</span></strong> — ");
    t = t.replace(/\+\+([\s\S]+?)\+\+/g, function (_, inner) {
      var visible = inner.replace(/<[^>]+>/g, "");
      return visible.length > 90 ? inner : "<span class=\"ul\">" + inner + "</span>";
    });
    t = t.replace(/\*\*([\s\S]+?)\*\*/g, "<strong>$1</strong>");
    t = t.replace(/(^|[\s(])\*([^*\n]+)\*/g, "$1<em>$2</em>");
    return t;
  }

  function slug(text) {
    return text
      .toLowerCase()
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .replace(/&amp;/g, "")
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-|-$/g, "")
      .slice(0, 64);
  }

  function isSubhead(text) {
    var n = text.toLowerCase();
    return n.indexOf("professionisti") === 0 || n.indexOf("ristoranti") === 0;
  }

  function parseCurve(code) {
    var nodes = [];
    var styles = {};
    var nodeRe = /(\w+)\["([\s\S]*?)"\]/g;
    var match;
    while ((match = nodeRe.exec(code))) {
      var parts = match[2].split(/<br\s*\/?>/i).map(function (part) { return part.trim(); }).filter(Boolean);
      nodes.push({ id: match[1], name: parts[0] || "", pct: parts[1] || "", desc: parts.slice(2).join(" ") });
    }
    var styleRe = /style\s+(\w+)\s+fill:(#[0-9A-Fa-f]+)\s*,\s*color:(#[0-9A-Fa-f]+)/g;
    while ((match = styleRe.exec(code))) styles[match[1]] = { fill: match[2] };
    var max = nodes.reduce(function (top, node) {
      return Math.max(top, Number(String(node.pct).replace("%", "").replace(",", ".")) || 0);
    }, 1);
    return nodes.map(function (node) {
      var value = Number(String(node.pct).replace("%", "").replace(",", ".")) || 0;
      return {
        name: node.name,
        pct: node.pct,
        desc: node.desc,
        fill: (styles[node.id] && styles[node.id].fill) || "#1B4332",
        width: Math.max(8, Math.round((value / max) * 100))
      };
    });
  }

  function parseBlocks(md) {
    var lines = md.split("\n");
    var blocks = [];
    var i = 0;
    while (i < lines.length) {
      var line = lines[i];
      if (!line.trim()) { i++; continue; }
      if (line.trim().indexOf("<!--") === 0) {
        while (i < lines.length && lines[i].indexOf("-->") === -1) i++;
        i++;
        continue;
      }
      if (line.trim() === "---") { i++; continue; }
      if (line.indexOf("```") === 0) {
        var lang = line.slice(3).trim().toLowerCase();
        var buf = [];
        i++;
        while (i < lines.length && lines[i].indexOf("```") !== 0) {
          buf.push(lines[i]);
          i++;
        }
        if (i < lines.length) i++;
        blocks.push({ type: "code", lang: lang, text: buf.join("\n") });
        continue;
      }
      var heading = /^(#{1,6})\s+(.*)$/.exec(line);
      if (heading) {
        blocks.push({ type: "heading", level: heading[1].length, text: heading[2].trim() });
        i++;
        continue;
      }
      if (/^\s*\|/.test(line)) {
        var rows = [];
        while (i < lines.length && /^\s*\|/.test(lines[i])) {
          var cells = lines[i].trim().replace(/^\|/, "").replace(/\|$/, "").split("|").map(function (cell) {
            return cell.trim();
          });
          if (!cells.every(function (cell) { return /^:?-+:?$/.test(cell); })) rows.push(cells);
          i++;
        }
        blocks.push({ type: "table", rows: rows });
        continue;
      }
      if (/^[-*]\s+/.test(line)) {
        var items = [];
        while (i < lines.length && /^[-*]\s+/.test(lines[i])) {
          var parts = [lines[i].replace(/^[-*]\s+/, "")];
          i++;
          while (i < lines.length) {
            if (!lines[i].trim()) {
              if (i + 1 < lines.length && /^ {2,}\S/.test(lines[i + 1])) { i++; continue; }
              break;
            }
            if (/^ {2,}\S/.test(lines[i])) {
              parts.push(lines[i].trim());
              i++;
              continue;
            }
            break;
          }
          items.push(parts);
        }
        blocks.push({ type: "list", items: items });
        continue;
      }
      if (/^>/.test(line)) {
        var quote = [];
        while (i < lines.length && /^>/.test(lines[i])) {
          quote.push(lines[i].replace(/^>\s?/, ""));
          i++;
        }
        var paras = [];
        var current = [];
        quote.forEach(function (part) {
          if (!part.trim()) {
            if (current.length) paras.push(current.join(" "));
            current = [];
          } else current.push(part.trim());
        });
        if (current.length) paras.push(current.join(" "));
        blocks.push({ type: "quote", paras: paras });
        continue;
      }
      var para = [line.trim()];
      i++;
      while (i < lines.length && lines[i].trim() && !/^(#{1,6}\s|[-*]\s|>|```|\s*\|)/.test(lines[i]) && lines[i].trim() !== "---") {
        para.push(lines[i].trim());
        i++;
      }
      blocks.push({ type: "paragraph", text: para.join(" ") });
    }
    return blocks;
  }

  function renderCurve(code) {
    var stages = parseCurve(code);
    var label = stages.map(function (stage) { return stage.name + " " + stage.pct; }).join(", ");
    return "<figure class=\"curve\" aria-label=\"" + escapeHtml(label) + "\">" + stages.map(function (stage) {
      return "<div class=\"stage\">" +
        "<div class=\"stage-top\"><span>" + escapeHtml(stage.name) + "</span><span class=\"pct\">" + escapeHtml(stage.pct) + "</span></div>" +
        "<div class=\"track\"><div class=\"fill\" style=\"width:" + stage.width + "%;background:" + stage.fill + "\"></div></div>" +
        "<p>" + escapeHtml(stage.desc) + "</p></div>";
    }).join("") + "</figure>";
  }

  function renderTable(rows) {
    var head = rows[0] || [];
    var body = rows.slice(1);
    var cls = String(head[0] || "").toLowerCase() === "anno" ? "years" : "prose";
    return "<div class=\"table-wrap\"><table class=\"" + cls + "\"><thead><tr>" + head.map(function (cell) {
      return "<th scope=\"col\">" + inline(cell) + "</th>";
    }).join("") + "</tr></thead><tbody>" + body.map(function (row) {
      return "<tr>" + row.map(function (cell) { return "<td>" + inline(cell) + "</td>"; }).join("") + "</tr>";
    }).join("") + "</tbody></table></div>";
  }

  function renderBlocks(blocks) {
    return blocks.map(function (block) {
      if (block.type === "heading") {
        if (block.level === 1) return "";
        var id = slug(block.text);
        if (block.level === 2) {
          var cls = isSubhead(block.text) ? "subhead" : "chapter";
          return "<h2 class=\"" + cls + "\" id=\"" + id + "\">" + inline(block.text) + "</h2>";
        }
        return "<h3 id=\"" + id + "\">" + inline(block.text) + "</h3>";
      }
      if (block.type === "paragraph") {
        var lead = /^\*\*[\s\S]+\*\*$/.test(block.text.trim());
        return "<p" + (lead ? " class=\"lead\"" : "") + ">" + inline(block.text) + "</p>";
      }
      if (block.type === "list") {
        return "<ul>" + block.items.map(function (parts) {
          return "<li>" + inline(parts[0]) + parts.slice(1).map(function (part) {
            return "<p>" + inline(part) + "</p>";
          }).join("") + "</li>";
        }).join("") + "</ul>";
      }
      if (block.type === "quote") {
        return "<blockquote>" + block.paras.map(function (para) {
          return "<p>" + inline(para) + "</p>";
        }).join("") + "</blockquote>";
      }
      if (block.type === "table") return renderTable(block.rows);
      if (block.type === "code" && block.lang === "mermaid") return renderCurve(block.text);
      if (block.type === "code") return "<pre>" + escapeHtml(block.text) + "</pre>";
      return "";
    }).join("\n");
  }

  function tocHtml(blocks) {
    var items = [];
    blocks.forEach(function (block) {
      if (block.type !== "heading" || block.level !== 2) return;
      var entry = "<a href=\"#" + slug(block.text) + "\">" + inline(block.text) + "</a>";
      if (isSubhead(block.text) && items.length) items[items.length - 1].children.push(entry);
      else items.push({ entry: entry, children: [] });
    });
    return "<ol class=\"toc\">" + items.map(function (item) {
      var nested = item.children.length
        ? "<ol>" + item.children.map(function (child) { return "<li>" + child + "</li>"; }).join("") + "</ol>"
        : "";
      return "<li>" + item.entry + nested + "</li>";
    }).join("") + "</ol>";
  }

  function stamp(title) {
    var now = new Date();
    var two = function (n) { return (n < 10 ? "0" : "") + n; };
    return two(now.getDate()) + "/" + two(now.getMonth() + 1) + "/" + now.getFullYear() + " " + title;
  }

  function renderDocument(markdown) {
    var start = markdown.search(/^# (?!Guida\b)/m);
    var body = start >= 0 ? markdown.slice(start) : markdown;
    var blocks = parseBlocks(body);
    var titleBlock = blocks.filter(function (block) { return block.type === "heading" && block.level === 1; })[0];
    var title = titleBlock ? titleBlock.text : "TAB";
    var line = stamp(title);
    document.title = title;
    var foot = document.getElementById("print-footer");
    if (!foot) {
      foot = document.createElement("style");
      foot.id = "print-footer";
      document.head.appendChild(foot);
    }
    foot.textContent = "@page{@bottom-left{content:\"" + line.replace(/\\/g, "\\\\").replace(/"/g, "\\\"") + "\";font-family:\"Suisse\",\"Helvetica Neue\",Helvetica,Arial,sans-serif;font-size:9pt;color:#0F444D;}}";
    report.innerHTML =
      "<section class=\"cover\">" +
        "<div><h1>" + inline(title) + "</h1></div>" +
        "<nav aria-label=\"Executive Summary\"><p class=\"toc-label\">Executive Summary</p>" + tocHtml(blocks) + "</nav>" +
        "<p class=\"meta\">Novembre 2026</p>" +
      "</section><main>" + renderBlocks(blocks) + "</main>" +
      "<p class=\"sheet-foot\"><span>" + escapeHtml(line) + "</span></p>";
  }

  function readSource() {
    if (location.protocol === "file:") {
      return Promise.reject(new Error("file"));
    }
    return fetch(new URL(SOURCE, document.baseURI).href, { cache: "no-store" }).then(function (res) {
      if (!res.ok) throw new Error("Risposta " + res.status);
      return res.text();
    });
  }

  function showError(error) {
    var message = error && error.message === "file"
      ? "Apri la pagina da un server locale, nella stessa cartella del progetto."
      : "Non riesco a leggere BUSINESS_MODEL.md.";
    status.textContent = message;
    report.innerHTML = "<p class=\"dek\">" + message + "</p>";
  }

  function load() {
    status.textContent = "Lettura di BUSINESS_MODEL.md…";
    button.disabled = true;
    return readSource().then(function (markdown) {
      renderDocument(markdown);
      status.textContent = "Testo riletto da BUSINESS_MODEL.md.";
    }).catch(showError).then(function () {
      button.disabled = false;
    });
  }

  button.addEventListener("click", function () {
    status.textContent = "Preparo il PDF…";
    button.disabled = true;
    fetch("pdf", { cache: "no-store" }).then(function (res) {
      if (!res.ok) throw new Error("pdf");
      return res.blob();
    }).then(function (blob) {
      var url = URL.createObjectURL(blob);
      var link = document.createElement("a");
      link.href = url;
      link.download = "TAB-BMC.pdf";
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
      status.textContent = "PDF scaricato. Data e titolo sono solo nel footer.";
    }).catch(function () {
      status.textContent = "Non riesco a generare il PDF.";
    }).then(function () {
      button.disabled = false;
    });
  });

  load();
})();
