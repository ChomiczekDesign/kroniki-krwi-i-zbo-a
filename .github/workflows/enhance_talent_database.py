from pathlib import Path
import re

PUBLIC_DIR = Path("./public")

SCRIPT = r'''<script id="talent-database-js">
(() => {
  const DB_MARKER = "data-talent-database-enhanced";
  const collator = new Intl.Collator("pl", {
    numeric: true,
    sensitivity: "base"
  });
  const previewCache = new Map();

  function normalize(value) {
    return (value || "")
      .replace(/\s+/g, " ")
      .trim()
      .toLocaleLowerCase("pl");
  }

  function headerName(th) {
    return normalize(th.textContent)
      .replace(/[▲▼↕]/g, "")
      .trim();
  }

  function findTalentTables(root = document) {
    return [...root.querySelectorAll("table")].filter((table) => {
      if (table.hasAttribute(DB_MARKER)) return false;

      const headers = [...table.querySelectorAll("thead th")].map(headerName);

      // Minimalny zestaw, który odróżnia Bazę Talentów od innych tabel wiki.
      return (
        headers.includes("tier") &&
        headers.includes("typ") &&
        headers.includes("aktywacja")
      );
    });
  }

  function getHeaderMap(table) {
    const map = new Map();
    [...table.querySelectorAll("thead th")].forEach((th, index) => {
      map.set(headerName(th), index);
    });
    return map;
  }

  function cellText(row, index) {
    if (index === undefined) return "";
    const cell = row.cells[index];
    return cell ? cell.textContent.trim() : "";
  }

  function cellIsTrue(row, index) {
    if (index === undefined) return false;
    const cell = row.cells[index];
    if (!cell) return false;

    const checkbox = cell.querySelector('input[type="checkbox"]');
    if (checkbox) return checkbox.checked;

    const value = normalize(cell.textContent);
    return ["true", "tak", "yes", "1", "✓", "✔"].includes(value);
  }

  function splitMultiValue(value) {
    return value
      .split(/[,;|]/)
      .map((part) => part.trim())
      .filter(Boolean);
  }

  function addOptions(select, values) {
    [...new Set(values.filter(Boolean))]
      .sort((a, b) => collator.compare(a, b))
      .forEach((value) => {
        const option = document.createElement("option");
        option.value = value;
        option.textContent = value;
        select.appendChild(option);
      });
  }

  function makeSelect(labelText) {
    const label = document.createElement("label");
    label.className = "talent-db-filter";

    const caption = document.createElement("span");
    caption.textContent = labelText;

    const select = document.createElement("select");
    const all = document.createElement("option");
    all.value = "";
    all.textContent = "Wszystkie";
    select.appendChild(all);

    label.append(caption, select);
    return { label, select };
  }

  async function fetchPreview(url) {
    if (previewCache.has(url)) {
      return previewCache.get(url);
    }

    const promise = fetch(url, { credentials: "same-origin" })
      .then((response) => {
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }
        return response.text();
      })
      .then((html) => {
        const doc = new DOMParser().parseFromString(html, "text/html");
        const metaBox = doc.querySelector(".talent-meta-box");

        // Najpewniejszy przypadek: nasz box metadanych znajduje się bezpośrednio
        // przed treścią talentu. Bierzemy wszystko, co występuje po nim.
        if (metaBox && metaBox.parentElement) {
          const holder = document.createElement("div");
          let node = metaBox.nextSibling;

          while (node) {
            if (
              node.nodeType !== Node.ELEMENT_NODE ||
              !["SCRIPT", "STYLE"].includes(node.tagName)
            ) {
              holder.appendChild(node.cloneNode(true));
            }
            node = node.nextSibling;
          }

          if (holder.textContent.trim()) {
            return holder.innerHTML;
          }
        }

        // Fallback na wypadek zmiany struktury HTML przez Kiln.
        const source =
          doc.querySelector("main article") ||
          doc.querySelector("article") ||
          doc.querySelector("main");

        if (!source) {
          throw new Error("Nie znaleziono treści talentu na stronie.");
        }

        const clone = source.cloneNode(true);
        clone.querySelectorAll(
          "h1, .talent-meta-box, script, style, nav, .toc, .table-of-contents, .backlinks, .local-graph"
        ).forEach((element) => element.remove());

        return clone.innerHTML;
      });

    previewCache.set(url, promise);
    return promise;
  }

  function setupTable(table) {
    table.setAttribute(DB_MARKER, "true");
    table.classList.add("talent-db-table");

    const thead = table.querySelector("thead");
    const tbody = table.querySelector("tbody");
    if (!thead || !tbody) return;

    const headerMap = getHeaderMap(table);
    const tierIndex = headerMap.get("tier");
    const typeIndex = headerMap.get("typ");
    const activationIndex = headerMap.get("aktywacja");
    const rankedIndex = headerMap.get("ranked");

    const rows = [...tbody.querySelectorAll(":scope > tr")];
    if (!rows.length) return;

    rows.forEach((row, index) => {
      row.classList.add("talent-db-row");
      row.dataset.originalIndex = String(index);
      row.dataset.tier = cellText(row, tierIndex);
      row.dataset.type = cellText(row, typeIndex);
      row.dataset.activation = cellText(row, activationIndex);
      row.dataset.ranked = cellIsTrue(row, rankedIndex) ? "true" : "false";
      row.dataset.search = normalize(row.textContent);

      const firstCell = row.cells[0];
      if (!firstCell) return;

      const link = firstCell.querySelector("a[href]");
      if (!link) return;

      const button = document.createElement("button");
      button.type = "button";
      button.className = "talent-preview-toggle";
      button.setAttribute("aria-expanded", "false");
      button.setAttribute("aria-label", `Rozwiń podgląd: ${link.textContent.trim()}`);
      button.textContent = "▶";
      firstCell.prepend(button);

      const togglePreview = async () => {
        let previewRow = row.nextElementSibling;
        if (!previewRow || !previewRow.classList.contains("talent-preview-row")) {
          previewRow = document.createElement("tr");
          previewRow.className = "talent-preview-row";
          previewRow.hidden = true;

          const previewCell = document.createElement("td");
          previewCell.colSpan = row.cells.length;
          previewCell.innerHTML = '<div class="talent-preview-content talent-preview-loading">Ładowanie…</div>';
          previewRow.appendChild(previewCell);
          row.after(previewRow);
        }

        const willOpen = previewRow.hidden;
        previewRow.hidden = !willOpen;
        row.classList.toggle("talent-db-row-open", willOpen);
        button.textContent = willOpen ? "▼" : "▶";
        button.setAttribute("aria-expanded", willOpen ? "true" : "false");

        if (!willOpen || previewRow.dataset.loaded === "true") {
          return;
        }

        const content = previewRow.querySelector(".talent-preview-content");

        try {
          const previewHtml = await fetchPreview(link.href);
          content.classList.remove("talent-preview-loading");
          content.innerHTML = `
            <div class="talent-preview-description">${previewHtml}</div>
            <div class="talent-preview-footer">
              <a href="${link.href}">Otwórz pełną stronę →</a>
            </div>
          `;
          previewRow.dataset.loaded = "true";
        } catch (error) {
          content.classList.remove("talent-preview-loading");
          content.innerHTML = `
            <p>Nie udało się załadować podglądu talentu.</p>
            <div class="talent-preview-footer">
              <a href="${link.href}">Otwórz pełną stronę →</a>
            </div>
          `;
          console.error("Talent preview error:", error);
        }
      };

      button.addEventListener("click", (event) => {
        event.preventDefault();
        event.stopPropagation();
        togglePreview();
      });

      row.addEventListener("click", (event) => {
        if (event.target.closest("a, button, input, select, label")) return;
        togglePreview();
      });
    });

    const controls = document.createElement("div");
    controls.className = "talent-db-controls";

    const searchLabel = document.createElement("label");
    searchLabel.className = "talent-db-search";
    const searchCaption = document.createElement("span");
    searchCaption.textContent = "Szukaj";
    const search = document.createElement("input");
    search.type = "search";
    search.placeholder = "Nazwa, typ, aktywacja…";
    searchLabel.append(searchCaption, search);

    const tier = makeSelect("Tier");
    const type = makeSelect("Typ");
    const activation = makeSelect("Aktywacja");

    addOptions(tier.select, rows.map((row) => row.dataset.tier));
    addOptions(
      type.select,
      rows.flatMap((row) => splitMultiValue(row.dataset.type))
    );
    addOptions(
      activation.select,
      rows.map((row) => row.dataset.activation)
    );

    const rankedLabel = document.createElement("label");
    rankedLabel.className = "talent-db-ranked";
    const ranked = document.createElement("input");
    ranked.type = "checkbox";
    rankedLabel.append(ranked, document.createTextNode(" Tylko rankingowe"));

    const clear = document.createElement("button");
    clear.type = "button";
    clear.className = "talent-db-clear";
    clear.textContent = "Wyczyść filtry";

    const count = document.createElement("div");
    count.className = "talent-db-count";

    controls.append(
      searchLabel,
      tier.label,
      type.label,
      activation.label,
      rankedLabel,
      clear,
      count
    );

    const wrapper = document.createElement("div");
    wrapper.className = "talent-db-wrapper";
    table.parentNode.insertBefore(wrapper, table);
    wrapper.appendChild(controls);
    wrapper.appendChild(table);

    function applyFilters() {
      const query = normalize(search.value);
      const selectedTier = tier.select.value;
      const selectedType = type.select.value;
      const selectedActivation = activation.select.value;
      const onlyRanked = ranked.checked;
      let visible = 0;

      rows.forEach((row) => {
        const matchesSearch = !query || row.dataset.search.includes(query);
        const matchesTier = !selectedTier || row.dataset.tier === selectedTier;
        const matchesType =
          !selectedType || splitMultiValue(row.dataset.type).includes(selectedType);
        const matchesActivation =
          !selectedActivation || row.dataset.activation === selectedActivation;
        const matchesRanked = !onlyRanked || row.dataset.ranked === "true";

        const show =
          matchesSearch &&
          matchesTier &&
          matchesType &&
          matchesActivation &&
          matchesRanked;

        row.hidden = !show;

        const preview = row.nextElementSibling;
        if (preview && preview.classList.contains("talent-preview-row")) {
          if (!show) preview.hidden = true;
          else if (row.classList.contains("talent-db-row-open")) preview.hidden = false;
        }

        if (show) visible += 1;
      });

      count.textContent = `${visible} / ${rows.length} talentów`;
    }

    [search, tier.select, type.select, activation.select, ranked].forEach((control) => {
      control.addEventListener(control === search ? "input" : "change", applyFilters);
    });

    clear.addEventListener("click", () => {
      search.value = "";
      tier.select.value = "";
      type.select.value = "";
      activation.select.value = "";
      ranked.checked = false;
      applyFilters();
      search.focus();
    });

    let sortIndex = null;
    let sortDirection = 1;

    [...thead.querySelectorAll("th")].forEach((th, index) => {
      th.classList.add("talent-db-sortable");
      th.setAttribute("tabindex", "0");
      th.setAttribute("role", "button");
      th.setAttribute("aria-sort", "none");

      const arrow = document.createElement("span");
      arrow.className = "talent-sort-arrow";
      th.appendChild(arrow);

      const sort = () => {
        if (sortIndex === index) {
          sortDirection *= -1;
        } else {
          sortIndex = index;
          sortDirection = 1;
        }

        [...thead.querySelectorAll("th")].forEach((other) => {
          other.setAttribute("aria-sort", "none");
          const otherArrow = other.querySelector(".talent-sort-arrow");
          if (otherArrow) otherArrow.textContent = "";
        });

        th.setAttribute(
          "aria-sort",
          sortDirection === 1 ? "ascending" : "descending"
        );
        arrow.textContent = sortDirection === 1 ? " ▲" : " ▼";

        const sortedRows = [...rows].sort((a, b) => {
          const aValue = cellText(a, index);
          const bValue = cellText(b, index);

          const aNumber = Number(aValue.replace(",", "."));
          const bNumber = Number(bValue.replace(",", "."));

          let result;
          if (Number.isFinite(aNumber) && Number.isFinite(bNumber)) {
            result = aNumber - bNumber;
          } else {
            result = collator.compare(aValue, bValue);
          }

          if (result === 0) {
            result = Number(a.dataset.originalIndex) - Number(b.dataset.originalIndex);
          }

          return result * sortDirection;
        });

        sortedRows.forEach((row) => {
          const preview =
            row.nextElementSibling &&
            row.nextElementSibling.classList.contains("talent-preview-row")
              ? row.nextElementSibling
              : null;

          tbody.appendChild(row);
          if (preview) tbody.appendChild(preview);
        });
      };

      th.addEventListener("click", sort);
      th.addEventListener("keydown", (event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          sort();
        }
      });
    });

    applyFilters();
  }

  function initTalentDatabase(root = document) {
    findTalentTables(root).forEach(setupTable);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => initTalentDatabase());
  } else {
    initTalentDatabase();
  }

  // Kiln korzysta z HTMX/hx-boost, więc po przejściu na stronę bazy
  // bez pełnego reloadu musimy ponownie uruchomić inicjalizację.
  document.addEventListener("htmx:afterSwap", (event) => {
    initTalentDatabase(event.target || document);
  });
})();
</script>'''


def main():
    if not PUBLIC_DIR.exists():
        raise FileNotFoundError(
            f"Nie znaleziono {PUBLIC_DIR}. Uruchom najpierw build Kilna."
        )

    processed = 0

    for path in PUBLIC_DIR.rglob("*.html"):
        html = path.read_text(encoding="utf-8")

        # Usuń starszą wersję, jeśli skrypt zostałby uruchomiony ponownie.
        html = re.sub(
            r'\s*<script id="talent-database-js">.*?</script>',
            "",
            html,
            flags=re.DOTALL,
        )

        if "</body>" in html:
            html = html.replace("</body>", SCRIPT + "\n</body>", 1)
        else:
            html += "\n" + SCRIPT

        path.write_text(html, encoding="utf-8")
        processed += 1

    print(f"[OK] Dodano obsługę bazy talentów do {processed} stron HTML.")


if __name__ == "__main__":
    main()
