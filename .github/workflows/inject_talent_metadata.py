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
    Prosty parser frontmatteru dla talentów.

    Obsługuje np.:

    Tier: "1"
    Ranked: false
    Aktywacja: Pasywny
    Typ:
      - Wiedza
      - Motywacje
    """

    data = {}
    current_key = None

    for raw_line in frontmatter_text.splitlines():
        if not raw_line.strip():
            continue

        list_match = re.match(
            r"^\s*-\s+(.+?)\s*$",
            raw_line
        )

        if list_match and current_key:
            if not isinstance(
                data.get(current_key),
                list
            ):
                data[current_key] = []

            data[current_key].append(
                clean_scalar(
                    list_match.group(1)
                )
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
    Pozwala obsługiwać zarówno polskie,
    jak i alternatywne nazwy pól.
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
        return [
            str(item)
            for item in value
        ]

    return [str(value)]


def build_metadata_box(data: dict) -> str:
    tier = get_property(
        data,
        "tier",
        "Tier",
    )

    ranked = get_property(
        data,
        "ranked",
        "Ranked",
    )

    activation = get_property(
        data,
        "aktywacja",
        "Aktywacja",
        "activation",
        "Activation",
    )

    types = normalize_list(
        get_property(
            data,
            "typ",
            "Typ",
            "type",
            "Type",
        )
    )

    columns = []

    if tier is not None:
        columns.append(
            (
                "Tier",
                escape(str(tier))
            )
        )

    if activation:
        columns.append(
            (
                "Aktywacja",
                escape(str(activation))
            )
        )

    if types:
        columns.append(
            (
                "Typ",
                escape(", ".join(types))
            )
        )

    if is_true(ranked):
        columns.append(
            (
                "Rankingowy",
                "Tak"
            )
        )

    if not columns:
        return ""

    items = []

    for label, value in columns:
        items.append(
            '<div class="talent-meta-item">'
            f'<div class="talent-meta-label">{label}</div>'
            f'<div class="talent-meta-value">{value}</div>'
            '</div>'
        )

    return (
        '<div class="talent-meta-box">\n'
        + "\n".join(
            f"  {item}"
            for item in items
        )
        + "\n</div>"
    )


def extract_source_frontmatter(
    source_text: str,
):
    source_match = FRONTMATTER_RE.match(
        source_text
    )

    if not source_match:
        return None

    frontmatter_block = (
        source_match
        .group(0)
        .rstrip()
    )

    frontmatter_content = (
        source_match
        .group(1)
    )

    return (
        frontmatter_block,
        frontmatter_content,
    )


def remove_frontmatter_from_built(
    built_text: str,
    frontmatter_block: str,
) -> str:
    """
    replace_dice_tags.py może dołożyć własny <style>
    przed frontmatterem.

    Dlatego szukamy dokładnego bloku YAML
    w wygenerowanym pliku i usuwamy go
    z obecnej pozycji.
    """

    position = built_text.find(
        frontmatter_block
    )

    if position == -1:
        raise RuntimeError(
            "Nie znaleziono frontmatteru "
            "w przetworzonym pliku."
        )

    before = built_text[:position]

    after = built_text[
        position + len(frontmatter_block):
    ]

    return (
        before + after
    ).strip()


def split_dice_style(content: str):
    """
    Jeśli replace_dice_tags.py dodał
    blok <style> z klasą dice-inline,
    oddzielamy go od reszty treści.
    """

    content = content.strip()

    if (
        content.startswith("<style>")
        and "dice-inline" in content
    ):
        style_end = content.find(
            "</style>"
        )

        if style_end != -1:
            style_end += len("</style>")

            style_block = (
                content[:style_end]
                .strip()
            )

            body = (
                content[style_end:]
                .strip()
            )

            return style_block, body

    return None, content


def build_final_content(
    frontmatter_block: str,
    content_without_frontmatter: str,
    box: str,
) -> str:
    """
    Docelowa kolejność:

    ---
    frontmatter
    ---

    <style>kości</style>

    <div class="talent-meta-box">
      ...
    </div>

    treść talentu
    """

    style_block, body = split_dice_style(
        content_without_frontmatter
    )

    parts = [
        frontmatter_block
    ]

    if style_block:
        parts.append(style_block)

    if box:
        parts.append(box)

    if body:
        parts.append(body)

    return (
        "\n\n".join(parts)
        + "\n"
    )


def process_talent(
    source_path: Path
) -> bool:
    relative = source_path.relative_to(
        SRC_DIR
    )

    built_path = (
        BUILD_DIR / relative
    )

    if not built_path.exists():
        print(
            "[POMINIETO] "
            "Brak odpowiednika "
            f"w wiki_build: {relative}"
        )
        return False

    source_text = source_path.read_text(
        encoding="utf-8"
    )

    built_text = built_path.read_text(
        encoding="utf-8"
    )

    frontmatter = (
        extract_source_frontmatter(
            source_text
        )
    )

    if not frontmatter:
        print(
            "[POMINIETO] "
            f"Brak frontmatteru: {relative}"
        )
        return False

    (
        frontmatter_block,
        frontmatter_content,
    ) = frontmatter

    metadata = parse_frontmatter(
        frontmatter_content
    )

    box = build_metadata_box(
        metadata
    )

    content_without_frontmatter = (
        remove_frontmatter_from_built(
            built_text,
            frontmatter_block,
        )
    )

    updated = build_final_content(
        frontmatter_block,
        content_without_frontmatter,
        box,
    )

    built_path.write_text(
        updated,
        encoding="utf-8",
    )

    print(
        f"[OK] {relative}"
    )

    return True


def main():
    if not SRC_DIR.exists():
        print(
            "[INFO] Folder talentów "
            "jeszcze nie istnieje: "
            f"{SRC_DIR}"
        )
        return

    if not BUILD_DIR.exists():
        raise FileNotFoundError(
            f"Nie znaleziono {BUILD_DIR}. "
            "Uruchom najpierw "
            "replace_dice_tags.py."
        )

    processed = 0

    for source_path in sorted(
        SRC_DIR.rglob("*.md")
    ):
        if process_talent(
            source_path
        ):
            processed += 1

    print(
        "[OK] Przetworzono "
        f"metadane talentów: {processed}"
    )


if __name__ == "__main__":
    main()
