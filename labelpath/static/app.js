(function () {
  "use strict";

  function $(id) {
    return document.getElementById(id);
  }

  function escapeHtml(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function text(value, fallback) {
    var raw = value == null || value === "" ? fallback : value;
    return escapeHtml(raw);
  }

  function setStatus(id, message, state) {
    var node = $(id);
    node.textContent = message || "";
    node.setAttribute("data-state", state || "idle");
  }

  function sourceBlock(source) {
    if (!source) {
      return '<p class="muted">No source pointer on this edge.</p>';
    }
    var parts = [];
    if (source.kind) {
      parts.push('<p>Section: <strong>' + text(source.kind) + "</strong></p>");
    }
    if (source.snippet) {
      parts.push('<p class="snippet">' + text(source.snippet) + "</p>");
    }
    if (source.note) {
      parts.push('<p class="muted">' + text(source.note) + "</p>");
    }
    if (source.source_url) {
      parts.push(
        '<p><a href="' +
          text(source.source_url) +
          '" rel="noopener noreferrer" target="_blank">DailyMed label' +
          (source.set_id ? " (set_id " + text(source.set_id) + ")" : "") +
          "</a></p>"
      );
    } else if (source.set_id) {
      parts.push('<p class="muted">Label set_id: ' + text(source.set_id) + "</p>");
    }
    return parts.join("") || '<p class="muted">No section snippet for this edge.</p>';
  }

  function entityLine(item) {
    if (!item) {
      return "";
    }
    var name = item.generic_name || item.name || item.key || "";
    var bits = '<span class="kind">' + text(item.kind || "Node") + "</span> <strong>" + text(name) + "</strong>";
    if (item.key && item.key !== name) {
      bits += ' <span class="muted">(' + text(item.key) + ")</span>";
    }
    return bits;
  }

  function walkStep(path, index) {
    var nodes = path.nodes || [];
    var steps = path.steps || [];
    var left = nodes[index] || {};
    var right = nodes[index + 1] || {};
    var step = steps[index] || {};
    var storedFrom = step.from_key;
    var reversed = storedFrom && left.key && storedFrom !== left.key;
    return {
      left: left,
      right: right,
      rel: step.rel_type || "RELATED",
      reversed: reversed,
      source: step.source || null,
    };
  }

  function drawDiagram(path) {
    var nodes = path.nodes || [];
    if (!nodes.length) {
      return "";
    }
    var boxW = 158;
    var boxH = 52;
    var gap = 136;
    var padX = 16;
    var width = padX * 2 + nodes.length * boxW + Math.max(nodes.length - 1, 0) * gap;
    var height = 112;
    var svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("viewBox", "0 0 " + width + " " + height);
    svg.setAttribute("width", String(width));
    svg.setAttribute("height", String(height));
    svg.setAttribute("role", "img");
    var title = document.createElementNS("http://www.w3.org/2000/svg", "title");
    title.textContent = (nodes.map(function (n) { return n.name || n.key; }).join(" → "));
    svg.appendChild(title);

    function boxX(i) {
      return padX + i * (boxW + gap);
    }

    nodes.forEach(function (node, i) {
      if (i < nodes.length - 1) {
        var hop = walkStep(path, i);
        var x1 = boxX(i) + boxW;
        var x2 = boxX(i + 1);
        var mid = (x1 + x2) / 2;
        var line = document.createElementNS("http://www.w3.org/2000/svg", "line");
        line.setAttribute("x1", String(x1));
        line.setAttribute("y1", "56");
        line.setAttribute("x2", String(x2));
        line.setAttribute("y2", "56");
        line.setAttribute("stroke", "#8c2f12");
        line.setAttribute("stroke-width", "1.6");
        svg.appendChild(line);
        var label = document.createElementNS("http://www.w3.org/2000/svg", "text");
        label.setAttribute("x", String(mid));
        label.setAttribute("y", "28");
        label.setAttribute("text-anchor", "middle");
        label.setAttribute("fill", "#8c2f12");
        label.setAttribute("font-size", "10");
        label.setAttribute("font-family", "ui-sans-serif, system-ui, sans-serif");
        var relText = String(hop.rel || "").replace(/_/g, " ");
        if (hop.reversed) {
          relText += " (rev)";
        }
        label.textContent = relText;
        svg.appendChild(label);
      }

      var g = document.createElementNS("http://www.w3.org/2000/svg", "g");
      var rect = document.createElementNS("http://www.w3.org/2000/svg", "rect");
      rect.setAttribute("x", String(boxX(i)));
      rect.setAttribute("y", "34");
      rect.setAttribute("width", String(boxW));
      rect.setAttribute("height", String(boxH));
      rect.setAttribute("rx", "10");
      rect.setAttribute("fill", "#fffaf2");
      rect.setAttribute("stroke", "#241c15");
      rect.setAttribute("stroke-width", "1.2");
      g.appendChild(rect);
      var kind = document.createElementNS("http://www.w3.org/2000/svg", "text");
      kind.setAttribute("x", String(boxX(i) + boxW / 2));
      kind.setAttribute("y", "52");
      kind.setAttribute("text-anchor", "middle");
      kind.setAttribute("fill", "#6b5c4d");
      kind.setAttribute("font-size", "9");
      kind.setAttribute("font-family", "ui-sans-serif, system-ui, sans-serif");
      kind.textContent = node.kind || "";
      g.appendChild(kind);
      var name = document.createElementNS("http://www.w3.org/2000/svg", "text");
      name.setAttribute("x", String(boxX(i) + boxW / 2));
      name.setAttribute("y", "70");
      name.setAttribute("text-anchor", "middle");
      name.setAttribute("fill", "#241c15");
      name.setAttribute("font-size", "11");
      name.setAttribute("font-family", "Georgia, Palatino, serif");
      var labelText = node.name || node.key || "";
      if (labelText.length > 20) {
        labelText = labelText.slice(0, 18) + "…";
      }
      name.textContent = labelText;
      g.appendChild(name);
      svg.appendChild(g);
    });

    var defs = document.createElementNS("http://www.w3.org/2000/svg", "defs");
    var marker = document.createElementNS("http://www.w3.org/2000/svg", "marker");
    marker.setAttribute("id", "arrow-" + Math.random().toString(36).slice(2, 8));
    marker.setAttribute("viewBox", "0 0 10 7");
    marker.setAttribute("refX", "9");
    marker.setAttribute("refY", "3.5");
    marker.setAttribute("markerWidth", "8");
    marker.setAttribute("markerHeight", "7");
    marker.setAttribute("orient", "auto");
    var tip = document.createElementNS("http://www.w3.org/2000/svg", "path");
    tip.setAttribute("d", "M 0 0 L 10 3.5 L 0 7 z");
    tip.setAttribute("fill", "#8c2f12");
    marker.appendChild(tip);
    defs.appendChild(marker);
    svg.insertBefore(defs, svg.firstChild);
    // Point the edges at this unique marker.
    var markerId = marker.getAttribute("id");
    Array.prototype.forEach.call(svg.querySelectorAll("line"), function (line) {
      line.setAttribute("marker-end", "url(#" + markerId + ")");
    });

    var wrap = document.createElement("div");
    wrap.className = "diagram-wrap";
    wrap.appendChild(svg);
    return wrap;
  }

  function renderPaths(result) {
    var root = $("path-results");
    root.innerHTML = "";
    $("path-results").setAttribute("data-ready", result && result.found ? "yes" : "no");
    if (!result) {
      return;
    }
    if (result.error && !result.found) {
      return;
    }
    (result.paths || []).forEach(function (path, index) {
      var card = document.createElement("article");
      card.className = "card path-card";
      var heading = document.createElement("h3");
      var names = (path.nodes || []).map(function (n) { return n.name || n.key; }).join(" → ");
      heading.textContent = "Path " + (index + 1) + " (" + (path.hops || 0) + " hop" + (path.hops === 1 ? "" : "s") + "): " + names;
      card.appendChild(heading);
      card.appendChild(drawDiagram(path));
      (path.nodes || []).slice(0, -1).forEach(function (_, hopIndex) {
        var hop = walkStep(path, hopIndex);
        var block = document.createElement("div");
        block.className = "hop";
        block.innerHTML =
          "<p><strong>" +
          text(hop.left.name || hop.left.key) +
          "</strong> → <em>" +
          text(hop.rel) +
          "</em> → <strong>" +
          text(hop.right.name || hop.right.key) +
          "</strong>" +
          (hop.reversed
            ? ' <span class="muted">(stored relationship points the other way)</span>'
            : "") +
          "</p>" +
          sourceBlock(hop.source);
        card.appendChild(block);
      });
      root.appendChild(card);
    });
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
          kind: item.kind || kindLabel || (item.source && item.source.kind),
          snippet: item.snippet || (item.source && item.source.snippet),
          source_url: item.source_url || (item.source && item.source.source_url),
          set_id: item.set_id || (item.source && item.source.set_id),
          note: item.source && item.source.note,
        });
        if (item.name) {
          var head = document.createElement("p");
          head.innerHTML = "<strong>" + text(item.name) + "</strong>";
          hop.insertBefore(head, hop.firstChild);
        }
        card.appendChild(hop);
      });
      root.appendChild(card);
    }
    section("Boxed warning", result.boxed_warnings, "boxed_warning");
    section("Contraindications", result.contraindication_sections, "contraindications");
    section("Contraindicated in", result.contraindicated_in, "contraindications");
  }

  function renderNeighbors(result) {
    var root = $("neighbors-results");
    root.innerHTML = "";
    if (result.drug) {
      var intro = document.createElement("p");
      intro.innerHTML = entityLine(result.drug);
      root.appendChild(intro);
    }
    var list = document.createElement("ul");
    list.className = "list";
    (result.neighbors || []).forEach(function (item) {
      var li = document.createElement("li");
      li.className = "card";
      var n = item.neighbor || {};
      var dir = item.direction === "incoming" ? "incoming" : "outgoing";
      li.innerHTML =
        "<h3>" +
        entityLine(n) +
        '</h3><p class="muted">' +
        text(dir) +
        " · " +
        text(item.rel_type) +
        "</p>" +
        sourceBlock(item.source);
      list.appendChild(li);
    });
    root.appendChild(list);
  }

  function request(url, statusId, onOk, emptyMessage) {
    setStatus(statusId, "Looking in the local snapshot…", "busy");
    return fetch(url)
      .then(function (res) {
        return res.json().then(function (body) {
          return { ok: res.ok, body: body };
        });
      })
      .then(function (payload) {
        var body = payload.body || {};
        if (!payload.ok || body.found === false) {
          setStatus(statusId, body.error || emptyMessage || "Nothing found in this snapshot.", "empty");
          return body;
        }
        setStatus(statusId, body.error || "", body.found ? "ok" : "idle");
        if (typeof onOk === "function") {
          onOk(body);
        }
        return body;
      })
      .catch(function () {
        setStatus(statusId, "The local LabelPath server could not be reached.", "error");
        return null;
      });
  }

  function runPaths() {
    var start = $("path-start").value.trim();
    var end = $("path-end").value.trim();
    var hops = $("path-hops").value || "2";
    if (!start || !end) {
      $("path-results").innerHTML = "";
      $("path-results").setAttribute("data-ready", "no");
      setStatus("path-status", "Enter two drug or ingredient names to look for a labeled path.", "empty");
      return;
    }
    var url =
      "/api/path?start=" +
      encodeURIComponent(start) +
      "&end=" +
      encodeURIComponent(end) +
      "&max_hops=" +
      encodeURIComponent(hops);
    request(url, "path-status", renderPaths, "No labeled path was found in this snapshot.").then(function (body) {
      if (body && body.found) {
        var count = (body.paths || []).length;
        setStatus(
          "path-status",
          count +
            " path" +
            (count === 1 ? "" : "s") +
            " of at most " +
            (body.max_hops || hops) +
            " hop" +
            (String(body.max_hops || hops) === "1" ? "" : "s") +
            ".",
          "ok"
        );
      }
    });
  }

  function runLookup() {
    var q = $("lookup-q").value.trim();
    if (!q) {
      $("lookup-results").innerHTML = "";
      setStatus("lookup-status", "Type a drug or ingredient name to search.", "empty");
      return;
    }
    request("/api/lookup?q=" + encodeURIComponent(q), "lookup-status", renderLookup, "No match in this snapshot.").then(
      function (body) {
        if (body && body.found) {
          setStatus("lookup-status", (body.matches || []).length + " match(es).", "ok");
        }
      }
    );
  }

  function runWarnings() {
    var q = $("warnings-q").value.trim();
    if (!q) {
      $("warnings-results").innerHTML = "";
      setStatus("warnings-status", "Type a drug name to list boxed warnings and contraindications.", "empty");
      return;
    }
    request("/api/warnings?q=" + encodeURIComponent(q), "warnings-status", renderWarnings, "No warnings found in this snapshot.");
  }

  function runNeighbors() {
    var q = $("neighbors-q").value.trim();
    if (!q) {
      $("neighbors-results").innerHTML = "";
      setStatus("neighbors-status", "Type a drug name to list labeled neighbors.", "empty");
      return;
    }
    request("/api/neighbors?q=" + encodeURIComponent(q), "neighbors-status", renderNeighbors, "No neighbors found in this snapshot.");
  }

  function fillDemo() {
    $("path-start").value = "apixaban";
    $("path-end").value = "aspirin";
    $("path-hops").value = "2";
    runPaths();
  }

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
  $("try-demo").addEventListener("click", fillDemo);

  if (/(?:\?|&)demo=1(?:&|$)/.test(window.location.search)) {
    fillDemo();
  }
})();
