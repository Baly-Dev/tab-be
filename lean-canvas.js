/* FlashTable Lean Canvas
   BUSINESS_MODEL.md è la fonte: a ogni caricamento il file viene riletto.
   <!-- start:problem --> … <!-- end:problem --> delimita il blocco.
   Lo stesso nome può aprirsi più volte. <u>testo</u> dentro è un punto di quel blocco.
   I punti modificati a mano restano in questo browser. «Dal documento» torna al file.
*/
(function (root) {
  var SOURCE = "BUSINESS_MODEL.md";
  var STORE = "flashtable.leanCanvas.points.v1";

  var BLOCKS = [
    { id: "problem", cls: "problem", title: "Problema", num: "1", en: "Problem" },
    { id: "solution", cls: "solution", title: "Soluzione", num: "4", en: "Solution", hint: "Nel testo integrale: attività, svolgimento, risorse e partner." },
    { id: "metrics", cls: "metrics", title: "Metriche chiave", num: "8", en: "Key Metrics" },
    { id: "uvp", cls: "uvp", title: "Proposta di valore", drawerTitle: "Proposta di valore unica", num: "3", en: "Unique Value Proposition" },
    { id: "unfair", cls: "unfair", title: "Vantaggio sleale", num: "9", en: "Unfair Advantage" },
    { id: "channels", cls: "channels", title: "Canali", num: "5", en: "Channels" },
    { id: "segments", cls: "segments", title: "Segmenti di clientela", num: "2", en: "Customer Segments" },
    { id: "cost", cls: "cost", title: "Struttura dei costi", num: "7", en: "Cost Structure" },
    { id: "revenue", cls: "revenue", title: "Flussi di ricavo", num: "6", en: "Revenue Streams" }
  ];

  function plain(s) {
    return String(s || "")
      .replace(/<u\b[^>]*>([\s\S]*?)<\/u>/gi, "$1")
      .replace(/\*\*/g, "")
      .replace(/\s+/g, " ")
      .trim();
  }

  function norm(s) {
    return plain(s).toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/[^a-z0-9]+/g, " ").trim();
  }

  function sentences(text) {
    return plain(text).split(/(?<=\.)\s+/).map(function (s) { return s.trim(); }).filter(Boolean);
  }

  function firstSentence(text) {
    var p = plain(text);
    var m = p.match(/^[\s\S]*?\.(?=\s|$)/);
    return m ? m[0] : p;
  }

  function escapeHtml(s) {
    return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }

  var BLOCK_ALIAS = {
    problem: "problem",
    problema: "problem",
    solution: "solution",
    soluzione: "solution",
    metrics: "metrics",
    metriche: "metrics",
    uvp: "uvp",
    value: "uvp",
    proposta: "uvp",
    valore: "uvp",
    unfair: "unfair",
    advantage: "unfair",
    vantaggio: "unfair",
    channels: "channels",
    canali: "channels",
    segments: "segments",
    segmenti: "segments",
    cost: "cost",
    costi: "cost",
    revenue: "revenue",
    ricavi: "revenue"
  };

  function resolveBlock(name) {
    var key = norm(name);
    if (BLOCK_ALIAS[key]) return BLOCK_ALIAS[key];
    var keys = Object.keys(BLOCK_ALIAS);
    for (var i = 0; i < keys.length; i++) {
      if (key.indexOf(keys[i]) !== -1) return BLOCK_ALIAS[keys[i]];
    }
    return null;
  }

  function inline(s) {
    var marks = [];
    var src = String(s).replace(/<u\b[^>]*>([\s\S]*?)<\/u>/gi, function (_, inner) {
      marks.push(inner);
      return "\u0000" + (marks.length - 1) + "\u0000";
    });
    var html = escapeHtml(src).replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
    return html.replace(/\u0000(\d+)\u0000/g, function (_, index) {
      return "<mark class=\"hl\">" + inline(marks[Number(index)]) + "</mark>";
    });
  }

  function marksInText(text, fallback) {
    var found = [];
    var re = /<u\b([^>]*)>([\s\S]*?)<\/u>/gi;
    var match;
    while ((match = re.exec(String(text || "")))) {
      var named = /block\s*=\s*["']([^"']+)["']/i.exec(match[1] || "");
      var id = named ? resolveBlock(named[1]) : fallback;
      var value = plain(match[2]);
      if (id && value) found.push({ id: id, text: value });
    }
    return found;
  }

  function marksInBlocks(blocks, fallback) {
    var found = [];
    (blocks || []).forEach(function (block) {
      if (block.type === "heading" || block.type === "paragraph") {
        found = found.concat(marksInText(block.text, fallback));
      } else if (block.type === "list") {
        block.items.forEach(function (item) {
          item.forEach(function (part) { found = found.concat(marksInText(part, fallback)); });
        });
      } else if (block.type === "table") {
        block.rows.forEach(function (row) {
          row.forEach(function (cell) { found = found.concat(marksInText(cell, fallback)); });
        });
      }
    });
    return found;
  }

  function hash(s) {
    var h = 2166136261;
    for (var i = 0; i < s.length; i++) {
      h ^= s.charCodeAt(i);
      h = Math.imul(h, 16777619);
    }
    return (h >>> 0).toString(16);
  }

  function clone(o) {
    return JSON.parse(JSON.stringify(o));
  }

  function parseMarkdown(src) {
    var lines = String(src).replace(/\r\n/g, "\n").split("\n");
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
          var cells = lines[i].trim().replace(/^\|/, "").replace(/\|$/, "").split("|").map(function (c) { return c.trim(); });
          var sep = cells.every(function (c) { return /^:?-+:?$/.test(c); });
          if (!sep) rows.push(cells);
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
            if (/^ {2,}\S/.test(lines[i])) {
              parts.push(lines[i].trim());
              i++;
              continue;
            }
            if (!lines[i].trim() && i + 1 < lines.length && /^ {2,}\S/.test(lines[i + 1])) {
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
      var para = [line.trim()];
      i++;
      while (i < lines.length && lines[i].trim() && !/^(#{1,6}\s|```|\s*\|)/.test(lines[i]) && !/^[-*]\s+/.test(lines[i]) && lines[i].trim() !== "---") {
        para.push(lines[i].trim());
        i++;
      }
      blocks.push({ type: "paragraph", text: para.join(" ") });
    }
    return blocks;
  }

  function splitSections(blocks) {
    var preamble = [];
    var sections = [];
    var current = null;
    blocks.forEach(function (block) {
      if (block.type === "heading" && block.level === 2) {
        current = { title: block.text, blocks: [] };
        sections.push(current);
      } else if (current) current.blocks.push(block);
      else preamble.push(block);
    });
    return { preamble: preamble, sections: sections };
  }

  function findSection(sections, test) {
    for (var i = 0; i < sections.length; i++) {
      if (test(norm(sections[i].title))) return sections[i];
    }
    return null;
  }

  function chunks(blocks) {
    var prelude = [];
    var parts = [];
    var current = null;
    blocks.forEach(function (block) {
      if (block.type === "heading" && block.level === 3) {
        current = { title: block.text, blocks: [] };
        parts.push(current);
      } else if (current) current.blocks.push(block);
      else prelude.push(block);
    });
    return { prelude: prelude, parts: parts };
  }

  function firstParagraph(blocks) {
    for (var i = 0; i < blocks.length; i++) {
      if (blocks[i].type === "paragraph") return blocks[i].text;
    }
    return "";
  }

  function tableBody(section) {
    if (!section) return [];
    for (var i = 0; i < section.blocks.length; i++) {
      if (section.blocks[i].type === "table") return section.blocks[i].rows.slice(1);
    }
    return [];
  }

  function summaryMap(section) {
    var map = {};
    tableBody(section).forEach(function (row) {
      map[norm(row[0])] = row[1] || "";
    });
    return map;
  }

  function paragraphsOf(blocks) {
    return blocks.filter(function (b) { return b.type === "paragraph"; }).map(function (b) { return b.text; });
  }

  function renderBlocks(blocks) {
    return blocks.map(function (block) {
      if (block.type === "heading") {
        var id = "h-" + norm(block.text).replace(/\s+/g, "-").slice(0, 48);
        var tag = block.level <= 2 ? "h3" : "h4";
        return "<" + tag + " id=\"" + id + "\">" + inline(block.text) + "</" + tag + ">";
      }
      if (block.type === "paragraph") return "<p>" + inline(block.text) + "</p>";
      if (block.type === "list") {
        return "<ul>" + block.items.map(function (parts) {
          return "<li>" + inline(parts[0]) + parts.slice(1).map(function (p) {
            return "<p>" + inline(p) + "</p>";
          }).join("") + "</li>";
        }).join("") + "</ul>";
      }
      if (block.type === "table") {
        var head = block.rows[0] || [];
        var body = block.rows.slice(1);
        var byYear = plain(head[0] || "").toLowerCase() === "anno";
        return "<div class=\"table-wrap\"><table" + (byYear ? " class=\"by-year\"" : "") + "><thead><tr>" + head.map(function (c) {
          return "<th scope=\"col\">" + inline(c) + "</th>";
        }).join("") + "</tr></thead><tbody>" + body.map(function (row) {
          return "<tr>" + row.map(function (c) { return "<td>" + inline(c) + "</td>"; }).join("") + "</tr>";
        }).join("") + "</tbody></table></div>";
      }
      if (block.type === "code" && block.lang === "mermaid") return curveHtml(block.text);
      if (block.type === "code") return "<pre class=\"code\">" + escapeHtml(block.text) + "</pre>";
      return "";
    }).join("");
  }

  function curveHtml(code) {
    var items = [];
    var re = /\["([\s\S]*?)"\]/g;
    var match;
    while ((match = re.exec(code))) {
      items.push(match[1].split(/<br\s*\/?>/i).map(function (s) { return s.trim(); }).filter(Boolean));
    }
    if (!items.length) return "<pre class=\"code\">" + escapeHtml(code) + "</pre>";
    return "<p class=\"diagram-note\">Nel documento questa curva è un diagramma. Stadi, percentuali e descrizioni sono quelli del diagramma.</p><ol class=\"curve\">" +
      items.map(function (parts) {
        var pct = "";
        parts.forEach(function (p) { if (/%$/.test(p)) pct = p; });
        var name = parts[0] || "";
        var desc = parts.filter(function (p) { return p !== pct && p !== name; }).join(" ");
        return "<li><span class=\"pct\">" + escapeHtml(pct) + "</span><strong>" + escapeHtml(name) + "</strong><span class=\"desc\">" + escapeHtml(desc) + "</span></li>";
      }).join("") + "</ol>";
  }

  function sectionHtml(section, synthesis) {
    if (!section) return "";
    var id = "s-" + norm(section.title).replace(/\s+/g, "-").slice(0, 48);
    var lead = synthesis ? "<p class=\"synthesis\"><span>In sintesi, nel documento</span>" + escapeHtml(plain(synthesis)) + "</p>" : "";
    return "<h3 id=\"" + id + "\">" + inline(section.title) + "</h3>" + lead + renderBlocks(section.blocks);
  }

  function partHtml(part) {
    var id = "s-" + norm(part.title).replace(/\s+/g, "-").slice(0, 48);
    return "<h3 id=\"" + id + "\">" + inline(part.title) + "</h3>" + renderBlocks(part.blocks);
  }

  function quoteParagraphs(sections, tests) {
    var found = [];
    sections.forEach(function (section) {
      section.blocks.forEach(function (block) {
        if (block.type !== "paragraph") return;
        var text = plain(block.text);
        tests.forEach(function (test) {
          if (text.toLowerCase().indexOf(test.q) !== -1) {
            found.push({ text: text, where: test.where || plain(section.title) });
          }
        });
      });
    });
    return found;
  }

  function splitCanvas(src) {
    var lines = String(src).replace(/\r\n/g, "\n").split("\n");
    var regions = {};
    var open = null;
    var buf = [];
    function close() {
      if (open) {
        var text = buf.join("\n").trim();
        if (text) {
          if (!regions[open]) regions[open] = [];
          regions[open].push(parseMarkdown(text));
        }
      }
      buf = [];
      open = null;
    }
    lines.forEach(function (line) {
      var start = /^\s*<!--\s*start[:\s]+([^>]+?)\s*-->\s*$/i.exec(line);
      var end = /^\s*<!--\s*end[:\s]+([^>]+?)\s*-->\s*$/i.exec(line);
      if (start) {
        close();
        open = resolveBlock(start[1]);
        return;
      }
      if (end) {
        close();
        return;
      }
      if (open) buf.push(line);
    });
    close();
    return regions;
  }

  function takeGuide(src) {
    var match = /<!--\s*canvas-guide\s*-->([\s\S]*?)<!--\s*\/canvas-guide\s*-->/.exec(src);
    return {
      guide: match ? match[1].trim() : "",
      markdown: match ? src.replace(match[0], "") : src
    };
  }

  function buildDocument(markdown) {
    var taken = takeGuide(markdown);
    markdown = taken.markdown;
    var parsed = splitSections(parseMarkdown(markdown));
    var sections = parsed.sections;
    var sec = {
      problem: findSection(sections, function (t) { return t === "il problema"; }),
      idea: findSection(sections, function (t) { return t === "l idea" || t === "idea"; }),
      canvas: findSection(sections, function (t) { return t.indexOf("canvas in una pagina") !== -1; }),
      segment: findSection(sections, function (t) { return t.indexOf("customer segment") !== -1; }),
      b2c: findSection(sections, function (t) { return t.indexOf("professionisti") !== -1 && t.indexOf("b2c") !== -1; }),
      b2b: findSection(sections, function (t) { return t.indexOf("ristoranti") !== -1 && t.indexOf("b2b") !== -1; }),
      value: findSection(sections, function (t) { return t.indexOf("proposta di valore") !== -1; }),
      channels: findSection(sections, function (t) { return /canali$/.test(t); }),
      relation: findSection(sections, function (t) { return t.indexOf("relazione") !== -1; }),
      revenue: findSection(sections, function (t) { return t.indexOf("flussi di ricavo") !== -1; }),
      resources: findSection(sections, function (t) { return t.indexOf("risorse chiave") !== -1; }),
      activities: findSection(sections, function (t) { return t.indexOf("attivita chiave") !== -1; }),
      partners: findSection(sections, function (t) { return t.indexOf("partner chiave") !== -1; }),
      cost: findSection(sections, function (t) { return t.indexOf("struttura dei costi") !== -1; }),
      play: findSection(sections, function (t) { return t.indexOf("come si svolge") !== -1; }),
      metrics: findSection(sections, function (t) { return t.indexOf("metriche") !== -1; }),
      unfair: findSection(sections, function (t) { return t.indexOf("unfair") !== -1 || t.indexOf("vantaggio sleale") !== -1; })
    };
    var sum = summaryMap(sec.canvas);
    var idea = sec.idea ? chunks(sec.idea.blocks) : { prelude: [], parts: [] };
    var trend = null;
    var products = [];
    idea.parts.forEach(function (part) {
      if (norm(part.title) === "il trend") trend = part;
      else products.push(part);
    });
    var preambleParas = paragraphsOf(parsed.preamble);
    var dek = preambleParas[0] || "";
    var productLine = preambleParas.filter(function (p) { return /business lunch/i.test(p) && /offerte flash/i.test(p); })[0] || "";
    var gesture = preambleParas.filter(function (p) { return /gesto|mercato di ingresso/i.test(p); })[0] || "";
    var hypothesis = "";
    preambleParas.concat(paragraphsOf(sec.revenue ? sec.revenue.blocks : [])).forEach(function (p) {
      if (!hypothesis && /ipotesi/i.test(p)) hypothesis = p;
    });

    var quotes = quoteParagraphs(sections, [
      { q: "visita, prenotazione e vendita", where: "Attività chiave" },
      { q: "si contano separatamente", where: "Canali" },
      { q: "non conta come locale pagante", where: "Flussi di ricavo" },
      { q: "da osservare sull'uso", where: "Proposta di valore" },
      { q: "da osservare sull’uso", where: "Proposta di valore" }
    ]);
    var community = quoteParagraphs(sections, [
      { q: "non una base di utenti già acquisita", where: "Canali" }
    ]);

    function missing(name) {
      return "<p>Sezione non trovata in BUSINESS_MODEL.md: " + escapeHtml(name) + ".</p>";
    }

    var regions = splitCanvas(markdown);
    function regionBlocks(id) {
      var all = [];
      (regions[id] || []).forEach(function (blocks) { all = all.concat(blocks); });
      return all;
    }
    function filled(id) { return regionBlocks(id).length > 0; }

    var drawers = {};
    BLOCKS.forEach(function (block) {
      var blocks = regionBlocks(block.id);
      if (blocks.length) drawers[block.id] = renderBlocks(blocks);
      else if (block.id === "metrics") drawers[block.id] = metricsDrawer(quotes);
      else if (block.id === "unfair") drawers[block.id] = unfairDrawer(community);
      else drawers[block.id] = "<h3>Da definire</h3><p>Nel file questo blocco non ha start e end.</p>";
    });

    var valueSyn = sum["proposta di valore"] || "";
    var quote = (valueSyn.match(/«[^»]+»/) || gesture.match(/«[^»]+»/) || [""])[0];
    var valueItems = valueSyn ? valueSyn.split(/(?=Per il )/i).map(plain).filter(Boolean) : [];

    var models = {
      problem: points(tableBody(sec.problem).map(function (row) { return plain(row[1]); })),
      segments: {
        type: "points",
        lead: "",
        note: "",
        groups: [
          { label: "", items: sentences(sum.segmenti || firstParagraph(sec.segment ? sec.segment.blocks : [])) },
          { label: "Relazione", items: sentences(sum.relazioni || firstParagraph(sec.relation ? sec.relation.blocks : [])) }
        ]
      },
      uvp: {
        type: "points",
        lead: quote,
        note: "",
        groups: [{ label: "", items: valueItems.length ? valueItems : sentences(valueSyn) }]
      },
      solution: points(products.map(function (part) {
        return plain(part.title) + ". " + firstSentence(firstParagraph(part.blocks));
      })),
      channels: points(sentences(sum.canali || firstParagraph(sec.channels ? sec.channels.blocks : []))),
      revenue: {
        type: "flows",
        flows: tableBody(sec.revenue).map(function (row) {
          return { label: plain(row[0]), value: plain(row[3] || ""), detail: plain(row[1] || "") };
        })
      },
      cost: {
        type: "voices",
        voices: tableBody(sec.cost).map(function (row) { return plain(row[0]); }),
        note: firstSentence(firstParagraph(sec.cost ? sec.cost.blocks : []))
      },
      metrics: sec.metrics ? pointsFromSection(sec.metrics) : { type: "text", text: "Il documento non fissa le metriche con cui leggere il business." },
      unfair: sec.unfair ? pointsFromSection(sec.unfair) : { type: "text", text: "Il documento non indica un vantaggio difficile da copiare o da comprare." }
    };

    ["problem", "segments", "uvp", "solution", "channels"].forEach(function (id) {
      var groups = models[id].groups || [];
      groups.forEach(function (group) {
        group.items = (group.items || []).map(plain).filter(Boolean);
        if (!group.items.length) group.items = [""];
      });
    });
    if (!models.revenue.flows.length) {
      models.revenue.flows = [{ label: "Flusso", value: "", detail: "" }];
    }
    if (!models.cost.voices.length) models.cost.voices = [""];

    var status = {};
    BLOCKS.forEach(function (block) {
      if (!filled(block.id)) status[block.id] = "tbd";
      else if (block.id === "revenue" && /ipotesi/i.test(textOf(regionBlocks("revenue")))) status[block.id] = "ipotesi";
      else status[block.id] = "definito";
    });

    var excerpts = {};
    BLOCKS.forEach(function (block) {
      var text = textOf(regionBlocks(block.id));
      if (text) excerpts[block.id] = text;
      else if (block.id === "metrics") excerpts[block.id] = "Il documento non dice quali numeri leggere per capire se il business funziona. " + quotes.map(function (q) { return q.text; }).join(" ");
      else if (block.id === "unfair") excerpts[block.id] = "Il documento non indica un vantaggio difficile da copiare o da comprare. " + community.map(function (q) { return q.text; }).join(" ");
      else excerpts[block.id] = "";
    });

    var filePoints = {};
    BLOCKS.forEach(function (block) { filePoints[block.id] = []; });
    function keep(mark) {
      if (!mark.id || !filePoints[mark.id]) return;
      var list = filePoints[mark.id];
      if (list.some(function (point) { return point.text === mark.text; })) return;
      list.push({ text: mark.text, quote: mark.text });
    }
    BLOCKS.forEach(function (block) {
      marksInBlocks(regionBlocks(block.id), block.id).forEach(keep);
    });

    return {
      dek: plain(dek),
      title: docTitle(parsed.preamble),
      models: models,
      excerpts: excerpts,
      filePoints: filePoints,
      drawers: drawers,
      guide: taken.guide ? renderBlocks(parseMarkdown(taken.guide)) : "",
      status: status
    };
  }

  function isAppParagraph(block) {
    return block.type === "paragraph" && /^flashtable è l.app/i.test(plain(block.text));
  }

  function docTitle(preamble) {
    for (var i = 0; i < preamble.length; i++) {
      if (preamble[i].type === "heading" && preamble[i].level === 1) {
        return plain(preamble[i].text).split(/[—–-]/)[0].trim() || "FlashTable";
      }
    }
    return "FlashTable";
  }

  function textOf(blocks) {
    var parts = [];
    (blocks || []).forEach(function (block) {
      if (block.type === "heading" || block.type === "paragraph") parts.push(plain(block.text));
      else if (block.type === "list") {
        block.items.forEach(function (item) {
          item.forEach(function (p) { parts.push(plain(p)); });
        });
      } else if (block.type === "table") {
        block.rows.forEach(function (row) {
          parts.push(row.map(plain).filter(Boolean).join(" · "));
        });
      } else if (block.type === "code" && block.lang === "mermaid") {
        var re = /\["([\s\S]*?)"\]/g;
        var match;
        while ((match = re.exec(block.text))) parts.push(plain(match[1].replace(/<br\s*\/?>/gi, " ")));
      }
    });
    return parts.map(function (p) { return p.trim(); }).filter(Boolean).join(" ");
  }

  function textSection(section) {
    if (!section) return "";
    return [plain(section.title), textOf(section.blocks)].filter(Boolean).join(" ");
  }

  function textPart(part) {
    return [plain(part.title), textOf(part.blocks)].filter(Boolean).join(" ");
  }

  function points(items) {
    return { type: "points", lead: "", note: "", groups: [{ label: "", items: items.filter(Boolean) }] };
  }

  function pointsFromSection(section) {
    var items = [];
    section.blocks.forEach(function (block) {
      if (block.type === "list") block.items.forEach(function (parts) { items.push(plain(parts[0])); });
      else if (block.type === "paragraph" && items.length < 4) items.push(firstSentence(block.text));
    });
    return points(items.slice(0, 6));
  }

  function toc(titles) {
    var links = titles.filter(Boolean).map(function (title) {
      var id = "s-" + norm(title).replace(/\s+/g, "-").slice(0, 48);
      return "<li><a href=\"#" + id + "\">" + escapeHtml(plain(title)) + "</a></li>";
    }).join("");
    return links ? "<ul class=\"toc\">" + links + "</ul>" : "";
  }

  function metricsDrawer(quotes) {
    var body = "<p class=\"map-note\">Nota di mappatura. BUSINESS_MODEL.md non definisce un set di metriche chiave. Non ne è stata aggiunta nessuna. Le frasi qui sotto, se presenti, sono citazioni: il testo integrale resta nella sezione di provenienza.</p><h3>Da definire</h3><p>Il documento non dice quali numeri leggere per capire se il business funziona.</p>";
    quotes.forEach(function (q) {
      body += "<blockquote><p>" + escapeHtml(q.text) + "</p><span class=\"attribution\">" + escapeHtml(q.where) + "</span></blockquote>";
    });
    return body;
  }

  function unfairDrawer(quotes) {
    var body = "<p class=\"map-note\">Nota di mappatura. Nel Lean Canvas questo blocco è un vantaggio difficile da copiare o da comprare. Il documento non ne indica uno.</p><h3>Da definire</h3><p>Risorse, partner e community di partenza restano nei pannelli Soluzione e Canali, non come vantaggio esclusivo.</p>";
    quotes.forEach(function (q) {
      body += "<blockquote><p>" + escapeHtml(q.text) + "</p><span class=\"attribution\">" + escapeHtml(q.where) + "</span></blockquote>";
    });
    return body;
  }

  root.LeanCanvas = { parseMarkdown: parseMarkdown, buildDocument: buildDocument };

  if (typeof document === "undefined") return;

  var canvas = document.getElementById("canvas");
  var drawer = document.getElementById("drawer");
  var drawerTitle = document.getElementById("drawer-title");
  var drawerKicker = document.getElementById("drawer-kicker");
  var drawerBody = document.getElementById("drawer-body");
  var closeBtn = document.getElementById("drawer-close");
  var guideBtn = document.getElementById("guide-open");
  var markBtn = document.getElementById("drawer-mark");
  var sourceState = document.getElementById("source-state");
  var docDek = document.getElementById("doc-dek");
  var docTitleEl = document.getElementById("doc-title");

  var built = null;
  var store = loadStore();
  var defaults = {};
  var hashes = {};
  var live = {};
  var openId = null;
  var pending = null;
  var lastFocus = null;

  function loadStore() {
    try { return JSON.parse(localStorage.getItem(STORE)) || {}; }
    catch (e) { return {}; }
  }

  function writeStore() {
    localStorage.setItem(STORE, JSON.stringify(store));
  }

  function statusWord(status) {
    if (status === "tbd") return "Da definire";
    if (status === "ipotesi") return "Listini da verificare";
    return "Definito";
  }

  function blockById(id) {
    for (var i = 0; i < BLOCKS.length; i++) if (BLOCKS[i].id === id) return BLOCKS[i];
    return null;
  }

  function renderAll() {
    canvas.innerHTML = "";
    BLOCKS.forEach(function (block) {
      var saved = store[block.id];
      var points = saved && Array.isArray(saved.points) ? clone(saved.points) : clone(defaults[block.id] || []);
      live[block.id] = { points: points };
      canvas.appendChild(renderCard(block));
    });
  }

  function renderCard(block) {
    var article = document.createElement("article");
    article.className = "block " + block.cls + (built.status[block.id] === "tbd" ? " tbd" : "");
    article.dataset.id = block.id;

    var btn = document.createElement("button");
    btn.type = "button";
    btn.className = "head-btn";
    btn.setAttribute("aria-expanded", "false");
    btn.setAttribute("aria-controls", "drawer");
    var head = document.createElement("span");
    head.className = "head";
    var h2 = document.createElement("h2");
    h2.textContent = block.title;
    var aside = document.createElement("span");
    aside.className = "head-aside";
    var num = document.createElement("span");
    num.className = "num";
    num.textContent = block.num;
    var chevron = document.createElement("span");
    chevron.className = "chevron";
    chevron.setAttribute("aria-hidden", "true");
    aside.appendChild(num);
    aside.appendChild(chevron);
    head.appendChild(h2);
    head.appendChild(aside);
    btn.appendChild(head);
    article.appendChild(btn);

    if (built.status[block.id] !== "definito") {
      var flag = document.createElement("p");
      flag.className = "flag";
      flag.textContent = statusWord(built.status[block.id]);
      article.appendChild(flag);
    }

    var excerpt = document.createElement("p");
    excerpt.className = "excerpt";
    excerpt.textContent = built.excerpts[block.id] || "";
    article.appendChild(excerpt);

    var points = live[block.id].points || [];
    if (points.length) {
      var ul = document.createElement("ul");
      ul.className = "points";
      points.forEach(function (point, index) {
        var li = document.createElement("li");
        if (point.quote) li.className = "from-quote";
        var span = editable("span", "text", point.text, { field: "item", index: index });
        li.appendChild(span);
        li.appendChild(removeButton({ kind: "item", index: index, label: "Rimuovi punto" }));
        ul.appendChild(li);
      });
      article.appendChild(ul);
    }

    var tools = document.createElement("div");
    tools.className = "card-tools";
    var add = document.createElement("button");
    add.type = "button";
    add.className = "text-btn add";
    add.textContent = "Aggiungi";
    var reset = document.createElement("button");
    reset.type = "button";
    reset.className = "text-btn reset";
    reset.textContent = "Dal documento";
    tools.appendChild(add);
    tools.appendChild(reset);
    article.appendChild(tools);
    syncTools(article);
    return article;
  }

  function editable(tag, cls, text, data) {
    var node = document.createElement(tag);
    if (cls) node.className = cls;
    node.contentEditable = "true";
    node.spellcheck = true;
    if (data.field) node.dataset.field = data.field;
    if (data.group != null) node.dataset.group = String(data.group);
    if (data.index != null) node.dataset.index = String(data.index);
    node.textContent = text || "";
    return node;
  }

  function removeButton(data) {
    var button = document.createElement("button");
    button.type = "button";
    button.className = "remove";
    button.textContent = "×";
    button.setAttribute("aria-label", data.label);
    button.dataset.kind = data.kind;
    if (data.group != null) button.dataset.group = String(data.group);
    button.dataset.index = String(data.index);
    return button;
  }

  function pointsKey(points) {
    return JSON.stringify((points || []).map(function (point) {
      return { text: point.text || "", quote: point.quote || null };
    }));
  }

  function isCustom(id) {
    return pointsKey(live[id].points) !== pointsKey(defaults[id]);
  }

  function isStale(id) {
    return !!(store[id] && store[id].base && store[id].base !== hashes[id]);
  }

  function syncTools(article) {
    var id = article.dataset.id;
    var reset = article.querySelector(".reset");
    var note = article.querySelector(".stale-note");
    if (note) note.remove();
    var custom = isCustom(id);
    var stale = isStale(id);
    reset.hidden = !custom && !stale;
    reset.textContent = stale ? "Aggiorna dal file" : "Dal documento";
    if (stale) {
      var p = document.createElement("p");
      p.className = "stale-note";
      p.textContent = "Le sottolineature nel file sono cambiate dopo questa modifica.";
      article.insertBefore(p, article.querySelector(".card-tools"));
    }
  }

  function saveLive(id) {
    if (!isCustom(id)) delete store[id];
    else store[id] = { points: clone(live[id].points), base: hashes[id] };
    writeStore();
  }

  function rerender(id, focus) {
    var block = blockById(id);
    var current = canvas.querySelector("[data-id='" + id + "']");
    var next = renderCard(block);
    if (drawer && !drawer.hidden && current.classList.contains("is-open")) {
      next.classList.add("is-open");
      next.querySelector(".head-btn").setAttribute("aria-expanded", "true");
    }
    current.replaceWith(next);
    if (!focus) return;
    var target = next.querySelector("[data-field='item'][data-index='" + focus.index + "']");
    if (target) target.focus();
  }

  function wrapNode(node) {
    if (!node || !node.parentNode || !node.textContent.trim()) return;
    var mark = document.createElement("mark");
    mark.className = "hl";
    node.parentNode.insertBefore(mark, node);
    mark.appendChild(node);
  }

  function wrapRange(range) {
    var root = range.commonAncestorContainer.nodeType === 1
      ? range.commonAncestorContainer
      : range.commonAncestorContainer.parentNode;
    if (!root || !drawerBody.contains(root)) return;
    var walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    var slices = [];
    var node;
    while ((node = walker.nextNode())) {
      if (!range.intersectsNode(node)) continue;
      if (node.parentElement && node.parentElement.closest("mark.hl")) continue;
      var from = node === range.startContainer ? range.startOffset : 0;
      var to = node === range.endContainer ? range.endOffset : node.textContent.length;
      if (to > from) slices.push({ node: node, from: from, to: to });
    }
    for (var i = slices.length - 1; i >= 0; i--) {
      var slice = slices[i];
      var current = slice.node;
      if (slice.to < current.textContent.length) current.splitText(slice.to);
      wrapNode(slice.from > 0 ? current.splitText(slice.from) : current);
    }
  }

  function markQuote(root, quote) {
    var needle = String(quote || "").replace(/\s+/g, " ").trim();
    if (!needle) return false;
    var walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    var nodes = [];
    var node;
    while ((node = walker.nextNode())) {
      if (node.parentElement && node.parentElement.closest("mark.hl")) continue;
      nodes.push(node);
    }
    var search = "";
    var indexMap = [];
    nodes.forEach(function (textNode, ni) {
      if (ni > 0 && search && search.charAt(search.length - 1) !== " ") {
        search += " ";
        indexMap.push(null);
      }
      var text = textNode.textContent;
      for (var i = 0; i < text.length; i++) {
        var ch = text.charAt(i);
        if (/\s/.test(ch)) {
          if (search && search.charAt(search.length - 1) !== " ") {
            search += " ";
            indexMap.push({ node: textNode, offset: i });
          }
        } else {
          search += ch;
          indexMap.push({ node: textNode, offset: i });
        }
      }
    });
    var at = search.indexOf(needle);
    if (at < 0) return false;
    var slices = [];
    var cursor = at;
    var end = at + needle.length;
    while (cursor < end) {
      while (cursor < end && !indexMap[cursor]) cursor++;
      if (cursor >= end) break;
      var owner = indexMap[cursor].node;
      var from = indexMap[cursor].offset;
      var to = from;
      while (cursor < end && indexMap[cursor] && indexMap[cursor].node === owner) {
        to = indexMap[cursor].offset + 1;
        cursor++;
      }
      slices.push({ node: owner, from: from, to: to });
    }
    for (var s = slices.length - 1; s >= 0; s--) {
      var slice = slices[s];
      var current = slice.node;
      if (!current.parentNode) continue;
      if (slice.to < current.textContent.length) current.splitText(slice.to);
      wrapNode(slice.from > 0 ? current.splitText(slice.from) : current);
    }
    return true;
  }

  function applyMarks(points) {
    var prose = drawerBody.querySelector(".prose");
    if (!prose) return;
    (points || []).forEach(function (point) {
      if (point.quote) markQuote(prose, point.quote);
    });
  }

  function selectionInside() {
    var sel = window.getSelection();
    if (!sel || sel.isCollapsed || !sel.rangeCount || drawer.hidden) return null;
    var range = sel.getRangeAt(0);
    if (!drawerBody.contains(range.commonAncestorContainer)) return null;
    var text = sel.toString().replace(/\s+/g, " ").trim();
    if (!text) return null;
    return { range: range.cloneRange(), text: text };
  }

  function syncMarkButton() {
    var found = selectionInside();
    if (found) pending = found;
    else pending = null;
    if (markBtn) markBtn.disabled = !pending;
  }

  function underline() {
    if (!openId || !pending) return;
    var text = pending.text;
    var points = live[openId].points;
    var exists = points.some(function (point) { return point.quote === text; });
    if (!exists) {
      wrapRange(pending.range);
      points.push({ text: text, quote: text });
      saveLive(openId);
      rerender(openId);
    }
    pending = null;
    if (markBtn) markBtn.disabled = true;
    var sel = window.getSelection();
    if (sel) sel.removeAllRanges();
  }

  function openDrawer(block, button) {
    canvas.querySelectorAll(".block").forEach(function (card) {
      var on = card.dataset.id === block.id;
      card.classList.toggle("is-open", on);
      card.querySelector(".head-btn").setAttribute("aria-expanded", on ? "true" : "false");
    });
    openId = block.id;
    drawerTitle.textContent = block.drawerTitle || block.title;
    drawerKicker.textContent = block.num + " · " + block.en + " · " + statusWord(built.status[block.id]);
    drawerBody.innerHTML = "<div class=\"prose\">" + (built.drawers[block.id] || "") + "</div>";
    applyMarks(live[block.id].points);
    drawerBody.scrollTop = 0;
    pending = null;
    if (markBtn) markBtn.disabled = true;
    var first = drawer.hidden;
    drawer.hidden = false;
    if (first) {
      lastFocus = button;
      closeBtn.focus();
    }
  }

  function openGuide(button) {
    canvas.querySelectorAll(".block").forEach(function (card) {
      card.classList.remove("is-open");
      card.querySelector(".head-btn").setAttribute("aria-expanded", "false");
    });
    openId = null;
    drawerTitle.textContent = "Guida";
    drawerKicker.textContent = "Come il file diventa il canvas";
    drawerBody.innerHTML = "<div class=\"prose\">" + (built && built.guide ? built.guide : "<p>Guida non trovata in BUSINESS_MODEL.md.</p>") + "</div>";
    drawerBody.scrollTop = 0;
    pending = null;
    if (markBtn) markBtn.disabled = true;
    var first = drawer.hidden;
    drawer.hidden = false;
    if (first) {
      lastFocus = button;
      closeBtn.focus();
    }
  }

  function closeDrawer() {
    drawer.hidden = true;
    openId = null;
    pending = null;
    if (markBtn) markBtn.disabled = true;
    canvas.querySelectorAll(".block").forEach(function (card) {
      card.classList.remove("is-open");
      card.querySelector(".head-btn").setAttribute("aria-expanded", "false");
    });
    if (lastFocus) lastFocus.focus();
  }

  canvas.addEventListener("click", function (event) {
    var head = event.target.closest(".head-btn");
    if (head) {
      var block = blockById(head.closest(".block").dataset.id);
      if (head.closest(".block").classList.contains("is-open")) closeDrawer();
      else openDrawer(block, head);
      return;
    }
    var reset = event.target.closest(".reset");
    if (reset) {
      var resetId = reset.closest(".block").dataset.id;
      delete store[resetId];
      writeStore();
      live[resetId] = { points: clone(defaults[resetId] || []) };
      if (openId === resetId) {
        drawerBody.innerHTML = "<div class=\"prose\">" + (built.drawers[resetId] || "") + "</div>";
        applyMarks(live[resetId].points);
      }
      rerender(resetId);
      return;
    }
    var add = event.target.closest(".add");
    if (add) {
      var addId = add.closest(".block").dataset.id;
      live[addId].points.push({ text: "", quote: null });
      saveLive(addId);
      rerender(addId, { index: live[addId].points.length - 1 });
      return;
    }
    var remove = event.target.closest(".remove");
    if (remove) {
      var removeId = remove.closest(".block").dataset.id;
      var index = Number(remove.dataset.index);
      var removed = live[removeId].points.splice(index, 1)[0];
      saveLive(removeId);
      if (openId === removeId && removed && removed.quote) {
        drawerBody.innerHTML = "<div class=\"prose\">" + (built.drawers[removeId] || "") + "</div>";
        applyMarks(live[removeId].points);
      }
      rerender(removeId);
    }
  });

  canvas.addEventListener("input", function (event) {
    if (!event.target.isContentEditable) return;
    var article = event.target.closest(".block");
    var id = article.dataset.id;
    var index = Number(event.target.dataset.index);
    if (event.target.dataset.field !== "item" || !live[id].points[index]) return;
    live[id].points[index].text = event.target.textContent.replace(/\n/g, " ");
    saveLive(id);
    syncTools(article);
  });

  canvas.addEventListener("keydown", function (event) {
    if (event.key === "Enter" && event.target.isContentEditable) event.preventDefault();
  });

  canvas.addEventListener("paste", function (event) {
    if (!event.target.isContentEditable) return;
    event.preventDefault();
    var text = (event.clipboardData || window.clipboardData).getData("text").replace(/\s+/g, " ").trim();
    document.execCommand("insertText", false, text);
  });

  closeBtn.addEventListener("click", closeDrawer);
  if (guideBtn) {
    guideBtn.addEventListener("click", function () {
      if (!drawer.hidden && drawerTitle.textContent === "Guida") closeDrawer();
      else openGuide(guideBtn);
    });
  }
  if (markBtn) {
    markBtn.addEventListener("mousedown", function (event) { event.preventDefault(); });
    markBtn.addEventListener("click", underline);
  }
  document.addEventListener("selectionchange", syncMarkButton);
  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape" && !drawer.hidden) {
      event.preventDefault();
      closeDrawer();
    }
  });

  drawer.addEventListener("keydown", function (event) {
    if (event.key !== "Tab" || drawer.hidden) return;
    var items = drawer.querySelectorAll("button, a[href]");
    if (!items.length) return;
    var first = items[0];
    var last = items[items.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  });

  drawerBody.addEventListener("click", function (event) {
    var link = event.target.closest("a[href^='#']");
    if (!link) return;
    var target = drawerBody.querySelector(link.getAttribute("href"));
    if (!target) return;
    event.preventDefault();
    var top = target.getBoundingClientRect().top - drawerBody.getBoundingClientRect().top + drawerBody.scrollTop - 12;
    drawerBody.scrollTo({ top: top, behavior: "smooth" });
  });

  function boot(markdown) {
    built = buildDocument(markdown);
    BLOCKS.forEach(function (block) {
      defaults[block.id] = built.filePoints[block.id] || [];
      hashes[block.id] = hash(JSON.stringify(defaults[block.id]));
    });
    if (docTitleEl) docTitleEl.textContent = built.title || "FlashTable";
    if (docDek) docDek.textContent = built.dek || "";
    renderAll();
    sourceState.textContent = "Testo riletto da BUSINESS_MODEL.md. start:problem e end:problem delimitano il blocco. <u> dentro è un punto.";
    sourceState.classList.remove("error");
  }

  function fail(message) {
    sourceState.textContent = message;
    sourceState.classList.add("error");
  }

  fetch(new URL(SOURCE, document.baseURI).href, { cache: "no-store" })
    .then(function (res) {
      if (!res.ok) throw new Error("Risposta " + res.status);
      return res.text();
    })
    .then(boot)
    .catch(function () {
      fail(location.protocol === "file:"
        ? "Il doppio clic non può leggere BUSINESS_MODEL.md. Apri http://127.0.0.1:8765/lean-canvas.html"
        : "BUSINESS_MODEL.md non è stato trovato accanto a questa pagina.");
    });
})(typeof window !== "undefined" ? window : globalThis);
