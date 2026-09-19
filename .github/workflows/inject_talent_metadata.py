from pathlib import Path
from html import escape
import re

SRC_DIR = Path("wiki/Mechaniki/Talenty")
BUILD_DIR = Path("wiki_build/Mechaniki/Talenty")

FRONTMATTER_RE = re.compile(
    r"\A---\s*\n(.*?)\n---\s*\n?",
    re.DOTALL,
)


def clean_scalar(value: str):
    value = value.strip()

    if (
        len(value) >= 2
        and value[0] == value[-1]
        and value[0] in {'"', "'"}
    ):
        value = value[1:-1]

    if value.lower() == "true":
        return True

    if value.lower() == "false":
        return False

    # Obsługa prostych list zapisanych jako:
    # typ: [Wiedza, Motywacje]
    if value.startswith("[") and value.endswith("]"):
        content = value[1:-1].strip()

        if not content:
            return []

        return [
            clean_scalar(item)
            for item in content.split(",")
        ]

    return value


def parse_frontmatter(frontmatter_text: str) -> dict:
    """
    Prosty parser wystarczający dla naszych metadanych talentów.

    Obsługuje np.:

    tier: 1
    ranked: false
    aktywacja: Pasywny
    typ:
      - Wiedza
      - Motywacje
    """

    data = {}
    current_key = None

    for raw_line in frontmatter_text.splitlines():
        if not raw_line.strip():
            continue

        # Element listy YAML
        list_match = re.match(r"^\s*-\s+(.+?)\s*$", raw_line)

        if list_match and current_key:
            if not isinstance(data.get(current_key), list):
                data[current_key] = []

            data[current_key].append(
                clean_scalar(list_match.group(1))
            )
            continue

        if ":" not in raw_line:
            continue

        key, value = raw_line.split(":", 1)

        key = key.strip()
        value = value.strip()
        current_key = key

        if value:
            data[key] = clean_scalar(value)
        else:
            data[key] = []


    return data


def get_property(data: dict, *names):
    """
    Pozwala używać zarówno:
      tier
    jak i:
      Tier

    Dzięki temu skrypt jest trochę odporniejszy na stare pliki.
    """

    for name in names:
        if name in data:
            return data[name]

    return None


def is_true(value) -> bool:
    if isinstance(value, bool):
        return value

    if value is None:
        return False

    return str(value).strip().lower() in {
        "true",
        "1",
        "yes",
        "tak",
    }


def normalize_list(value) -> list[str]:
    if value is None:
        return []

    if isinstance(value, list):
        return [str(item) for item in value]

    return [str(value)]


def build_metadata_box(data: dict) -> str:
    tier = get_property(data, "tier", "Tier")
    ranked = get_property(data, "ranked", "Ranked")
    activation = get_property(
        data,
        "aktywacja",
        "Aktywacja",
        "activation",
        "Activation",
    )
    types = normalize_list(
        get_property(data, "typ", "Typ", "type", "Type")
    )

    items = []

    if tier is not None:
        items.append(
            f'<span class="talent-meta-item talent-meta-tier">'
            f'<strong>Tier</strong> {escape(str(tier))}'
            f'</span>'
        )

    if activation:
        items.append(
            f'<span class="talent-meta-item">'
            f'{escape(str(activation))}'
            f'</span>'
        )

    for talent_type in types:
        items.append(
            f'<span class="talent-meta-item">'
            f'{escape(talent_type)}'
            f'</span>'
        )

    # Pokazujemy wyłącznie, jeśli ranked == true.
    if is_true(ranked):
        items.append(
            '<span class="talent-meta-item talent-meta-ranked">'
            'Rankingowy'
            '</span>'
        )

    if not items:
        return ""

    return (
        '<div class="talent-meta-box">\n'
        + "\n".join(f"  {item}" for item in items)
        + "\n</div>"
    )


def remove_and_restore_frontmatter(
    source_text: str,
    built_text: str,
):
    source_match = FRONTMATTER_RE.match(source_text)

    if not source_match:
        return None, None

    frontmatter_block = source_match.group(0).rstrip()
    frontmatter_content = source_match.group(1)

    # replace_dice_tags.py nie zmienia frontmatteru,
    # tylko dokleja przed nim swój <style>.
    # Szukamy więc dokładnego bloku źródłowego w wiki_build.
    position = built_text.find(frontmatter_block)

    if position == -1:
        raise RuntimeError(
            "Nie znaleziono frontmatteru w przetworzonym pliku."
        )

    content_without_frontmatter = (
        built_text[:position]
        + built_text[position + len(frontmatter_block):]
    ).strip()

    return (
        frontmatter_block,
        frontmatter_content,
        content_without_frontmatter,
    )


def insert_box_after_dice_style(
    frontmatter: str,
    content: str,
    box: str,
) -> str:
    """
    Docelowa kolejność:

    ---
    frontmatter
    ---

    <style>
      CSS kości
    </style>

    <div class="talent-meta-box">
      ...
    </div>

    Treść talentu
    """

    content = content.strip()

    # replace_dice_tags.py dokleja swój style block na początku.
    # Zostawiamy go tam, tylko frontmatter przenosimy nad niego.
    if content.startswith("<style>") and "dice-inline" in content:
        style_end = content.find("</style>")

        if style_end != -1:
            style_end += len("</style>")

            style_block = content[:style_end].strip()
            body = content[style_end:].strip()

            parts = [
                frontmatter,
                style_block,
            ]

            if box:
                parts.append(box)

            if body:
                parts.append(body)

            return "\n\n".join(parts) + "\n"

    parts = [frontmatter]

    if box:
        parts.append(box)

    if content:
        parts.append(content)

    return "\n\n".join(parts) + "\n"


def process_talent(source_path: Path) -> bool:
    relative = source_path.relative_to(SRC_DIR)
    built_path = BUILD_DIR / relative

    if not built_path.exists():
        print(
            f"[POMINIETO] Brak odpowiednika w wiki_build: "
            f"{relative}"
        )
        return False

    source_text = source_path.read_text(encoding="utf-8")
    built_text = built_path.read_text(encoding="utf-8")

    result = remove_and_restore_frontmatter(
        source_text,
        built_text,
    )

    if result[0] is None:
        print(
            f"[POMINIETO] Brak frontmatteru: {relative}"
        )
        return False

    (
        frontmatter_block,
        frontmatter_content,
        content_without_frontmatter,
    ) = result

    metadata = parse_frontmatter(frontmatter_content)
    box = build_metadata_box(metadata)

    updated = insert_box_after_dice_style(
        frontmatter_block,
        content_without_frontmatter,
        box,
    )

    built_path.write_text(
        updated,
        encoding="utf-8",
    )

    print(f"[OK] {relative}")
    return True


def main():
    if not SRC_DIR.exists():
        print(
            f"[INFO] Folder talentów jeszcze nie istnieje: "
            f"{SRC_DIR}"
        )
        return

    if not BUILD_DIR.exists():
        raise FileNotFoundError(
            f"Nie znaleziono {BUILD_DIR}. "
            "Uruchom najpierw replace_dice_tags.py."
        )

    processed = 0

    for source_path in sorted(SRC_DIR.rglob("*.md")):
        if process_talent(source_path):
            processed += 1

    print(
        f"[OK] Przetworzono metadane talentów: {processed}"
    )


if __name__ == "__main__":
    main()
