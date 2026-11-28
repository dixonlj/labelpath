(function () {
  "use strict";

  var FRIENDLY_LABELS = {
    LABELED_INTERACTION: "Mentions",
    CONTAINS: "Contains",
    INDICATED_FOR: "Indicated for",
    CONTRAINDICATED_IN: "Contraindicated in",
    drug_interactions: "Drug interactions",
    boxed_warning: "Boxed warning",
    warnings_and_cautions: "Warnings and cautions",
    contraindications: "Contraindications",
    indications_and_usage: "Indications and usage",
    adverse_reactions: "Adverse reactions"
  };

  var DAILYMED_LINK_TEXT =
    "Label on DailyMed (current version may differ from the snapshot)";

  var SVG_FONT =
    'Inter, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif';

  function $(id) {
    return document.getElementById(id);
  }

  function escapeHtml(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function text(value, fallback) {
    var raw = value == null || value === "" ? fallback : value;
    return escapeHtml(raw == null ? "" : raw);
  }

  function friendlyLabel(value) {
    var raw = value == null ? "" : String(value);
    if (!raw) {
      return "";
    }
    if (FRIENDLY_LABELS[raw]) {
      return FRIENDLY_LABELS[raw];
    }
    var spaced = raw.replace(/_/g, " ").replace(/\s+/g, " ").trim();
    if (!spaced) {
      return "";
    }
    return spaced.charAt(0).toUpperCase() + spaced.slice(1).toLowerCase();
  }

  function hopDisplayLabel(relType, sourceKind, sourceKinds) {
    var rel = friendlyLabel(relType);
    var kinds = [];
    var list = sourceKinds && sourceKinds.length ? sourceKinds : sourceKind ? [sourceKind] : [];
    list.forEach(function (kind) {
      var label = friendlyLabel(kind);
      if (label && kinds.indexOf(label) === -1) {
        kinds.push(label);
      }
    });
    return kinds.length ? rel + " · " + kinds.join(" · ") : rel;
  }

  function setStatus(id, message, state) {
    var el = $(id);
    if (!el) {
      return;
    }
    el.textContent = message || "";
    el.setAttribute("data-state", state || "idle");
  }

  function highlightSnippet(snippet, matchedName) {
    var escaped = text(snippet);
    if (!escaped || !matchedName) {
      return escaped;
    }
    var needle = String(matchedName).trim();
    if (!needle) {
      return escaped;
    }
    var pattern = new RegExp("(?<!\\w)" + needle.replace(/[.*+?^${}()|[\]\\]/g, "\\$&") + "(?!\\w)", "gi");
    return escaped.replace(pattern, "<mark class=\"hit\">$&</mark>");
  }

  function sourceBlock(source) {
    if (!source) {
      return "";
    }
    var parts = [];
    if (source.kind) {
      parts.push(
        '<p class="section-tag">Section: <strong>' +
          text(friendlyLabel(source.kind)) +
          "</strong></p>"
      );
    }
    if (source.snippet) {
      parts.push(
        '<blockquote class="snippet">' +
          highlightSnippet(source.snippet, source.matched_name) +
          "</blockquote>"
      );
    }
    if (source.note) {
      parts.push('<p class="muted">' + text(source.note) + "</p>");
    }
    if (source.source_url) {
      parts.push(
        '<p><a href="' +
          text(source.source_url) +
          '" rel="noopener noreferrer"' +
          (source.set_id ? ' title="FDA label ID ' + text(source.set_id) + '"' : "") +
          ">" +
          text(DAILYMED_LINK_TEXT) +
          "</a></p>"
      );
    } else if (source.set_id) {
      parts.push('<p class="muted">FDA label ID: ' + text(source.set_id) + "</p>");
    }
    return parts.join("");
  }

  function entityLine(item) {
    var kind = item.kind || item.type || "";
    var name = item.name || item.generic_name || item.key || "";
    var key = item.key && item.key !== name ? " (" + item.key + ")" : "";
    return (
      '<span class="entity"><span class="kind">' +
      text(kind) +
      "</span> " +
      text(name) +
      text(key) +
      "</span>"
    );
  }

  function walkStep(path, index) {
    var nodes = path.nodes || [];
    var steps = path.steps || [];
    var left = nodes[index] || {};
    var right = nodes[index + 1] || {};
    var step = steps[index] || {};
    var storedFrom = step.from_key;
    var reversed = storedFrom && left.key && storedFrom !== left.key;
    var sources = step.sources && step.sources.length ? step.sources : step.source ? [step.source] : [];
    return {
      left: left,
      right: right,
      fromKey: step.from_key,
      toKey: step.to_key,
      rel: step.rel_type || "RELATED",
      display: step.display_label || hopDisplayLabel(step.rel_type, null, step.source_kinds || (step.source && step.source.kind ? [step.source.kind] : [])),
      reversed: reversed,
      source: step.source || sources[0] || null,
      sources: sources
    };
  }

  function nodeCaption(node) {
    return node && (node.name || node.key) ? String(node.name || node.key) : "";
  }

  function drawDiagram(path) {
    var nodes = path.nodes || [];
    if (!nodes.length) {
      return "";
    }
    var boxW = 172;
    var boxH = 58;
    var gap = 220;
    var padX = 16;
    var width = padX * 2 + nodes.length * boxW + Math.max(nodes.length - 1, 0) * gap;
    var height = 128;
    var svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("viewBox", "0 0 " + width + " " + height);
    svg.setAttribute("width", String(width));
    svg.setAttribute("height", String(height));
    svg.setAttribute("role", "img");
    var title = document.createElementNS("http://www.w3.org/2000/svg", "title");
    title.textContent = nodes.map(nodeCaption).join(" → ");
    svg.appendChild(title);

    var defs = document.createElementNS("http://www.w3.org/2000/svg", "defs");
    var markerId = "arrow-" + Math.random().toString(36).slice(2, 8);
    var marker = document.createElementNS("http://www.w3.org/2000/svg", "marker");
    marker.setAttribute("id", markerId);
    marker.setAttribute("viewBox", "0 0 10 7");
    marker.setAttribute("refX", "9");
    marker.setAttribute("refY", "3.5");
    marker.setAttribute("markerWidth", "8");
    marker.setAttribute("markerHeight", "7");
    marker.setAttribute("orient", "auto");
    var tip = document.createElementNS("http://www.w3.org/2000/svg", "path");
    tip.setAttribute("d", "M 0 0 L 10 3.5 L 0 7 z");
    tip.setAttribute("fill", "#0e7c7b");
    marker.appendChild(tip);
    defs.appendChild(marker);
    svg.appendChild(defs);

    function boxX(i) {
      return padX + i * (boxW + gap);
    }

    nodes.forEach(function (node, i) {
      if (i < nodes.length - 1) {
        var hop = walkStep(path, i);
        var leftX = boxX(i) + boxW;
        var rightX = boxX(i + 1);
        var mid = (leftX + rightX) / 2;
        var line = document.createElementNS("http://www.w3.org/2000/svg", "line");
        // Arrow follows the true mention direction: the label that names a drug points to it.
        if (hop.reversed) {
          line.setAttribute("x1", String(rightX));
          line.setAttribute("x2", String(leftX));
        } else {
          line.setAttribute("x1", String(leftX));
          line.setAttribute("x2", String(rightX));
        }
        line.setAttribute("y1", "70");
        line.setAttribute("y2", "70");
        line.setAttribute("stroke", "#0e7c7b");
        line.setAttribute("stroke-width", "2");
        line.setAttribute("marker-end", "url(#" + markerId + ")");
        svg.appendChild(line);
        var label = document.createElementNS("http://www.w3.org/2000/svg", "text");
        label.setAttribute("x", String(mid));
        label.setAttribute("y", "48");
        label.setAttribute("text-anchor", "middle");
        label.setAttribute("fill", "#0a5f5e");
        label.setAttribute("font-size", "10");
        label.setAttribute("font-weight", "600");
        label.setAttribute("letter-spacing", "0.2");
        label.setAttribute("font-family", SVG_FONT);
        var display = String(hop.display || hop.rel || "");
        var parts = display.split(" · ");
        if (parts.length > 1) {
          var first = document.createElementNS("http://www.w3.org/2000/svg", "tspan");
          first.setAttribute("x", String(mid));
          first.setAttribute("dy", "0");
          first.textContent = parts[0];
          label.appendChild(first);
          var second = document.createElementNS("http://www.w3.org/2000/svg", "tspan");
          second.setAttribute("x", String(mid));
          second.setAttribute("dy", "12");
          second.textContent = parts.slice(1).join(" · ");
          label.appendChild(second);
        } else {
          label.textContent = display;
        }
        svg.appendChild(label);
      }

      var g = document.createElementNS("http://www.w3.org/2000/svg", "g");
      var rect = document.createElementNS("http://www.w3.org/2000/svg", "rect");
      rect.setAttribute("x", String(boxX(i)));
      rect.setAttribute("y", "41");
      rect.setAttribute("width", String(boxW));
      rect.setAttribute("height", String(boxH));
      rect.setAttribute("rx", "12");
      rect.setAttribute("fill", "#ffffff");
      rect.setAttribute("stroke", "#0b2545");
      rect.setAttribute("stroke-width", "1.5");
      g.appendChild(rect);
      var kind = document.createElementNS("http://www.w3.org/2000/svg", "text");
      kind.setAttribute("x", String(boxX(i) + boxW / 2));
      kind.setAttribute("y", "61");
      kind.setAttribute("text-anchor", "middle");
      kind.setAttribute("fill", "#5a6b7c");
      kind.setAttribute("font-size", "9.5");
      kind.setAttribute("font-weight", "600");
      kind.setAttribute("letter-spacing", "0.8");
      kind.setAttribute("font-family", SVG_FONT);
      kind.textContent = (node.kind || "").toUpperCase();
      g.appendChild(kind);
      var name = document.createElementNS("http://www.w3.org/2000/svg", "text");
      name.setAttribute("x", String(boxX(i) + boxW / 2));
      name.setAttribute("y", "82");
      name.setAttribute("text-anchor", "middle");
      name.setAttribute("fill", "#0b2545");
      name.setAttribute("font-size", "13");
      name.setAttribute("font-weight", "700");
      name.setAttribute("font-family", SVG_FONT);
      var labelText = nodeCaption(node);
      if (labelText.length > 20) {
        labelText = labelText.slice(0, 18) + "…";
      }
      name.textContent = labelText;
      g.appendChild(name);
      svg.appendChild(g);
    });

    var wrap = document.createElement("div");
    wrap.className = "diagram-wrap";
    wrap.appendChild(svg);
    return wrap;
  }

  function cypherToggle(result) {
    var cypher = (result && result.cypher) || {};
    if (!cypher.statement) {
      return null;
    }
    var details = document.createElement("details");
    details.className = "cypher-toggle";
    var summary = document.createElement("summary");
    summary.textContent = "Show Cypher";
    details.appendChild(summary);
    var pre = document.createElement("pre");
    pre.className = "cypher-block";
    var body = cypher.statement;
    if (cypher.parameters) {
      body += "\n\nParameters:\n" + JSON.stringify(cypher.parameters, null, 2);
    }
    pre.textContent = body;
    details.appendChild(pre);
    return details;
  }

  function appendCypher(root, result) {
    var toggle = cypherToggle(result);
    if (toggle) {
      root.appendChild(toggle);
    }
  }

  function renderPaths(result) {
    var root = $("path-results");
    root.innerHTML = "";
    root.setAttribute("data-ready", result && result.found ? "yes" : "no");
    if (!result) {
      return;
    }
    if (result.error && !result.found) {
      if (result.no_path_note) {
        var miss = document.createElement("p");
        miss.className = "path-note";
        miss.textContent = result.no_path_note;
        root.appendChild(miss);
      }
      appendCypher(root, result);
      return;
    }
    if (!result.direct_mention_found) {
      var neither = document.createElement("p");
      neither.className = "path-note";
      neither.textContent = "Neither endpoint label mentions the other directly.";
      root.appendChild(neither);
    }
    if (result.excluded_hubs && result.excluded_hubs.length && !result.include_hubs) {
      var hubs = document.createElement("p");
      hubs.className = "muted path-note";
      hubs.textContent =
        "Generic hub conditions excluded by default (contraindicated in more than " +
        (result.hub_condition_min_drugs || 10) +
        " drugs): " +
        result.excluded_hubs
          .map(function (item) {
            return (item.name || item.key) + " (" + item.drug_count + ")";
          })
          .join(", ") +
        ".";
      root.appendChild(hubs);
    }
    (result.paths || []).forEach(function (path, index) {
      var card = document.createElement("article");
      card.className = "card path-card";
      var head = document.createElement("div");
      head.className = "card-head";
      var names = (path.nodes || []).map(nodeCaption).join(" → ");
      var hopWord = (path.hops || 0) + " hop" + (path.hops === 1 ? "" : "s");
      var heading = document.createElement("h3");
      heading.className = "path-title";
      heading.textContent = "Path " + (index + 1);
      var badge = document.createElement("span");
      badge.className = "badge";
      badge.setAttribute("aria-hidden", "true");
      badge.textContent = String(index + 1);
      var count = document.createElement("span");
      count.className = "hop-count";
      count.textContent = hopWord;
      head.appendChild(badge);
      head.appendChild(heading);
      head.appendChild(count);
      card.appendChild(head);
      if (path.headline) {
        var headline = document.createElement("p");
        headline.className = "path-headline";
        headline.textContent = path.headline;
        card.appendChild(headline);
      }
      var route = document.createElement("p");
      route.className = "path-route";
      route.textContent = names;
      card.appendChild(route);
      if (path.note && result.direct_mention_found) {
        var note = document.createElement("p");
        note.className = "path-note";
        note.textContent = path.note;
        card.appendChild(note);
      }
      card.appendChild(drawDiagram(path));
      (path.nodes || []).slice(0, -1).forEach(function (_, hopIndex) {
        var hop = walkStep(path, hopIndex);
        var block = document.createElement("div");
        block.className = "hop";
        var fromNode = hop.reversed ? hop.right : hop.left;
        var toNode = hop.reversed ? hop.left : hop.right;
        var line = document.createElement("p");
        line.className = "hop-line";
        line.innerHTML =
          "<strong>" +
          text(nodeCaption(fromNode)) +
          '</strong> <span class="rel">' +
          text(hop.display || hop.rel) +
          "</span> <strong>" +
          text(nodeCaption(toNode)) +
          "</strong>";
        var num = document.createElement("span");
        num.className = "hop-num";
        num.setAttribute("aria-hidden", "true");
        num.textContent = String(hopIndex + 1);
        block.appendChild(num);
        block.appendChild(line);
        hop.sources.forEach(function (source) {
          var wrap = document.createElement("div");
          wrap.className = "source-item";
          wrap.innerHTML = sourceBlock(source);
          block.appendChild(wrap);
        });
        card.appendChild(block);
      });
      root.appendChild(card);
    });
    appendCypher(root, result);
  }

  function renderLookup(result) {
    var root = $("lookup-results");
    root.innerHTML = "";
    (result.matches || []).forEach(function (item) {
      var card = document.createElement("article");
      card.className = "card";
      var brands = (item.brand_names || []).join(", ");
      var apps = (item.application_numbers || []).join(", ");
      card.innerHTML =
        "<h3>" +
        entityLine(item) +
        "</h3>" +
        (brands ? '<p class="muted">Brand names: ' + text(brands) + "</p>" : "") +
        (apps ? '<p class="muted">Application numbers: ' + text(apps) + "</p>" : "");
      var use = document.createElement("button");
      use.type = "button";
      use.className = "btn ghost";
      use.textContent = "Use in path / warnings";
      use.addEventListener("click", function () {
        var name = item.generic_name || item.name || item.key;
        $("path-start").value = name;
        $("warnings-q").value = name;
        $("neighbors-q").value = name;
      });
      card.appendChild(use);
      root.appendChild(card);
    });
    appendCypher(root, result);
  }

  function renderWarnings(result) {
    var root = $("warnings-results");
    root.innerHTML = "";
    if (result.drug) {
      var intro = document.createElement("p");
      intro.innerHTML = entityLine(result.drug);
      root.appendChild(intro);
    }
    function section(title, items, kindLabel) {
      if (!items || !items.length) {
        return;
      }
      var card = document.createElement("article");
      card.className = "card";
      card.innerHTML = "<h3>" + text(title) + "</h3>";
      items.forEach(function (item) {
        var hop = document.createElement("div");
        hop.className = "hop";
        hop.innerHTML = sourceBlock({
          kind: item.kind || kindLabel,
          snippet: item.snippet,
          set_id: item.set_id || (item.source && item.source.set_id),
          source_url: item.source_url || (item.source && item.source.source_url),
          matched_name: item.matched_name || (item.source && item.source.matched_name)
        });
        card.appendChild(hop);
      });
      root.appendChild(card);
    }
    section("Boxed warnings", result.boxed_warnings, "boxed_warning");
    section("Contraindication sections", result.contraindication_sections, "contraindications");
    if (result.contraindicated_in && result.contraindicated_in.length) {
      var card = document.createElement("article");
      card.className = "card";
      card.innerHTML = "<h3>Contraindicated in</h3>";
      result.contraindicated_in.forEach(function (item) {
        var hop = document.createElement("div");
        hop.className = "hop";
        hop.innerHTML =
          "<p><strong>" +
          text(item.name || item.key) +
          "</strong></p>" +
          sourceBlock(item.source);
        card.appendChild(hop);
      });
      root.appendChild(card);
    }
    appendCypher(root, result);
  }

  function renderNeighbors(result) {
    var root = $("neighbors-results");
    root.innerHTML = "";
    if (result.drug) {
      var intro = document.createElement("p");
      intro.innerHTML = entityLine(result.drug);
      root.appendChild(intro);
    }
    (result.neighbors || []).forEach(function (item) {
      var card = document.createElement("article");
      card.className = "card";
      var neighbor = item.neighbor || {};
      var display =
        item.display_label ||
        hopDisplayLabel(item.rel_type, item.source && item.source.kind);
      var fromName, toName;
      if (item.direction === "outgoing") {
        fromName = (result.drug && (result.drug.name || result.drug.key)) || "drug";
        toName = neighbor.name || neighbor.key;
      } else {
        fromName = neighbor.name || neighbor.key;
        toName = (result.drug && (result.drug.name || result.drug.key)) || "drug";
      }
      card.innerHTML =
        "<p class=\"hop-line\"><strong>" +
        text(fromName) +
        '</strong> <span class="rel">' +
        text(display) +
        "</span> <strong>" +
        text(toName) +
        "</strong></p>" +
        sourceBlock(item.source);
      root.appendChild(card);
    });
    appendCypher(root, result);
  }

  function renderMedList(result) {
    var root = $("med-list-results");
    root.innerHTML = "";
    if (result.drugs && result.drugs.length) {
      var intro = document.createElement("p");
      intro.textContent =
        "Checking " +
        result.drugs
          .map(function (item) {
            return item.name || item.key;
          })
          .join(", ") +
        ".";
      root.appendChild(intro);
    }
    if (result.error && !result.found) {
      if (result.no_path_note) {
        var miss = document.createElement("p");
        miss.className = "path-note";
        miss.textContent = result.no_path_note;
        root.appendChild(miss);
      }
      appendCypher(root, result);
      return;
    }
    (result.pairs || []).forEach(function (pair) {
      var card = document.createElement("article");
      card.className = "card";
      var a = (pair.a && (pair.a.name || pair.a.key)) || "";
      var b = (pair.b && (pair.b.name || pair.b.key)) || "";
      var kind = pair.mutual
        ? "Mutual mentions"
        : pair.one_sided
          ? "One-sided mention"
          : "No mention in either direction";
      var heading = document.createElement("h3");
      heading.textContent = a + " — " + b;
      var badge = document.createElement("p");
      badge.className = "path-headline";
      badge.textContent = kind;
      card.appendChild(heading);
      card.appendChild(badge);
      [
        { label: a + " mentions " + b, payload: pair.a_mentions_b },
        { label: b + " mentions " + a, payload: pair.b_mentions_a }
      ].forEach(function (entry) {
        if (!entry.payload) {
          return;
        }
        var block = document.createElement("div");
        block.className = "hop";
        var line = document.createElement("p");
        line.className = "hop-line";
        line.innerHTML =
          "<strong>" +
          text(entry.payload.from_name || entry.label) +
          '</strong> <span class="rel">' +
          text(entry.payload.display_label || "Mentions") +
          "</span> <strong>" +
          text(entry.payload.to_name || "") +
          "</strong>";
        block.appendChild(line);
        (entry.payload.sources || []).forEach(function (source) {
          var wrap = document.createElement("div");
          wrap.className = "source-item";
          wrap.innerHTML = sourceBlock(source);
          block.appendChild(wrap);
        });
        card.appendChild(block);
      });
      if (pair.none) {
        var empty = document.createElement("p");
        empty.className = "muted";
        empty.textContent = "Neither label mentions the other in this snapshot.";
        card.appendChild(empty);
      }
      root.appendChild(card);
    });
    appendCypher(root, result);
  }

  function request(url, statusId, onOk, emptyMessage) {
    setStatus(statusId, "Searching this snapshot…", "busy");
    return fetch(url)
      .then(function (res) {
        return res.json().then(function (body) {
          return { ok: res.ok, body: body };
        });
      })
      .then(function (payload) {
        var body = payload.body || {};
        if (!payload.ok || body.found === false) {
          var message = body.error || emptyMessage || "Nothing was found in this snapshot.";
          if (body.no_path_note && message.indexOf(body.no_path_note) === -1) {
            message = message.replace(/\s*$/, "") + " " + body.no_path_note;
          }
          setStatus(statusId, message, body.error && payload.ok === false ? "error" : "empty");
          onOk(body);
          return body;
        }
        setStatus(statusId, "", "ok");
        onOk(body);
        return body;
      })
      .catch(function () {
        setStatus(statusId, "The local server could not complete that request.", "error");
      });
  }

  function runPaths() {
    var start = $("path-start").value.trim();
    var end = $("path-end").value.trim();
    var hops = $("path-hops").value;
    var includeHubs = $("include-hubs") && $("include-hubs").checked ? "1" : "0";
    var url =
      "/api/path?start=" +
      encodeURIComponent(start) +
      "&end=" +
      encodeURIComponent(end) +
      "&max_hops=" +
      encodeURIComponent(hops) +
      "&include_hubs=" +
      includeHubs;
    request(
      url,
      "path-status",
      renderPaths,
      "No labeled path was found in this snapshot."
    );
  }

  function parseMedList(raw) {
    return String(raw || "")
      .split(/[\n,;]+/)
      .map(function (item) {
        return item.trim();
      })
      .filter(Boolean);
  }

  function runMedList() {
    var names = parseMedList($("med-list-q").value);
    var url = "/api/med-list?q=" + encodeURIComponent(names.join(","));
    request(
      url,
      "med-list-status",
      renderMedList,
      "No label mentions among these drugs were found in this snapshot."
    );
  }

  function runLookup() {
    var q = $("lookup-q").value.trim();
    request(
      "/api/lookup?q=" + encodeURIComponent(q),
      "lookup-status",
      renderLookup,
      "No drug or ingredient by that name was found in this snapshot."
    );
  }

  function runWarnings() {
    var q = $("warnings-q").value.trim();
    request(
      "/api/warnings?q=" + encodeURIComponent(q),
      "warnings-status",
      renderWarnings,
      "No warnings found in this snapshot."
    );
  }

  function runNeighbors() {
    var q = $("neighbors-q").value.trim();
    request(
      "/api/neighbors?q=" + encodeURIComponent(q),
      "neighbors-status",
      renderNeighbors,
      "No neighbors found in this snapshot."
    );
  }

  function fillDemo() {
    $("path-start").value = "apixaban";
    $("path-end").value = "aspirin";
    $("path-hops").value = "2";
    runPaths();
  }

  function fillMedDemo() {
    $("med-list-q").value = "apixaban\naspirin\nwarfarin";
    runMedList();
  }

  function formatCount(n) {
    return Number(n).toLocaleString("en-US");
  }

  function applyMeta(meta) {
    if (!meta) {
      return;
    }
    ["snapshot-date-lede", "snapshot-date-footer"].forEach(function (id) {
      if ($(id) && meta.snapshot_date) {
        $(id).textContent = meta.snapshot_date;
      }
    });
    if ($("stat-pairs") && meta.mention_linked_pairs != null) {
      $("stat-pairs").textContent = formatCount(meta.mention_linked_pairs);
    }
    if ($("stat-mutual") && meta.mutual_mention_pairs != null) {
      $("stat-mutual").textContent = formatCount(meta.mutual_mention_pairs);
    }
    if ($("stat-onesided") && meta.one_sided_mention_pairs != null) {
      $("stat-onesided").textContent = formatCount(meta.one_sided_mention_pairs);
    }
    if ($("hub-toggle-label") && meta.hub_conditions && meta.hub_conditions.length) {
      var names = meta.hub_conditions
        .map(function (item) {
          return item.name || item.key;
        })
        .join(", ");
      $("hub-toggle-label").textContent =
        "Include generic hub conditions (" + names + ")";
    }
    if ($("most-mentioned-list") && meta.most_mentioned && meta.most_mentioned.length) {
      $("most-mentioned-list").innerHTML = meta.most_mentioned
        .slice(0, 3)
        .map(function (item) {
          return (
            "<li>" +
            text(item.name || item.key) +
            " — named by " +
            text(item.named_by) +
            " other drugs</li>"
          );
        })
        .join("");
    }
  }

  fetch("/api/meta")
    .then(function (res) {
      return res.json();
    })
    .then(applyMeta)
    .catch(function () {});

  $("path-form").addEventListener("submit", function (event) {
    event.preventDefault();
    runPaths();
  });
  $("lookup-form").addEventListener("submit", function (event) {
    event.preventDefault();
    runLookup();
  });
  $("warnings-form").addEventListener("submit", function (event) {
    event.preventDefault();
    runWarnings();
  });
  $("neighbors-form").addEventListener("submit", function (event) {
    event.preventDefault();
    runNeighbors();
  });
  $("med-list-form").addEventListener("submit", function (event) {
    event.preventDefault();
    runMedList();
  });
  $("try-demo").addEventListener("click", fillDemo);
  $("try-med-list").addEventListener("click", fillMedDemo);
  if (/[?&]demo=1(?:&|$)/.test(window.location.search)) {
    fillDemo();
  }
})();
