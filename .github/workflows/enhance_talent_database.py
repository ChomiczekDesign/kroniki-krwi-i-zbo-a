
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
