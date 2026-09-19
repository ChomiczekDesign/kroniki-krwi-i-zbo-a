from pathlib import Path
import base64
import re
import shutil
from urllib.parse import unquote_to_bytes

SRC_DIR = Path("wiki")
OUT_DIR = Path("wiki_build")
CSS_SOURCE = Path(".github/assets/StarWarsDice.css")

# Tagi wspierane przez skrypt
SUPPORTED_TAGS = {
    "Boost",
    "Setback",
    "Ability",
    "Difficulty",
    "Proficiency",
    "Challenge",
    "Force",
    "Success",
    "Failure",
    "Advantage",
    "Threat",
    "Triumph",
    "Despair",
    "LightDark",
    "LightSide",
    "DarkSide",
}

# Aliasy wpisywane w markdownzie
ALIASES = {
    "boost": "Boost",
    "setback": "Setback",
    "ability": "Ability",
    "difficulty": "Difficulty",
    "proficiency": "Proficiency",
    "challenge": "Challenge",
    "challange": "Challenge",
    "force": "Force",
    "success": "Success",
    "failure": "Failure",
    "advantage": "Advantage",
    "threat": "Threat",
    "triumph": "Triumph",
    "despair": "Despair",
    "lightdark": "LightDark",
    "light-dark": "LightDark",
    "lightside": "LightSide",
    "light-side": "LightSide",
    "darkside": "DarkSide",
    "dark-side": "DarkSide",
}

# Kości jako Unicode
DICE_STYLES = {
    "boost": ("■", "#87B4C8", "0.95em"),
    "setback": ("◻", "#f5f5f5", "1.05em"),
    "ability": ("⬧", "#53BC53", "1.00em"),
    "difficulty": ("⬧", "#7832C8", "1.00em"),
    "proficiency": ("⬣", "#FFFF50", "1.05em"),
    "challenge": ("⬣", "#E62832", "1.05em"),
    "force": ("⬣", "#f5f5f5", "1.05em"),
}

# Symbole wyników jako SVG/currentColor
SVG_SYMBOL_TAGS = {
    "Success",
    "Failure",
    "Advantage",
    "Threat",
    "Triumph",
    "Despair",
    "LightDark",
    "LightSide",
    "DarkSide",
}

# Znajduj #Tagi
TAG_PATTERN = re.compile(r'(?<![\w/])#([A-Za-z][A-Za-z\-]*)(?![\w-])')

# Wyciąganie data:image/svg+xml... z CSS
CSS_ICON_PATTERN = re.compile(
    r'href\^\="#(?P<name>[A-Za-z]+)"[\s\S]*?content:\s*url\("(?P<data>data:image/svg\+xml(?:;base64)?,[^"]+)"\);',
    re.MULTILINE,
)

INJECTED_STYLE = """
<style>
.dice-inline {
  display: inline-block;
  width: 0.95em;
  height: 0.95em;
  vertical-align: -0.12em;
  color: inherit;
  overflow: visible;
}
</style>
""".strip()


def extract_icons_from_css(css_text: str) -> dict[str, str]:
    icons: dict[str, str] = {}
    for match in CSS_ICON_PATTERN.finditer(css_text):
        name = match.group("name")
        data_uri = match.group("data")
        if name in SUPPORTED_TAGS and name not in icons:
            icons[name] = data_uri
    return icons


def decode_data_uri_to_svg(data_uri: str) -> str:
    header, payload = data_uri.split(",", 1)

    if ";base64" in header:
        raw = base64.b64decode(payload)
    else:
        raw = unquote_to_bytes(payload)

    return raw.decode("utf-8")


def normalize_svg(svg: str) -> str:
    svg = re.sub(r'^\s*<\?xml[^>]*>\s*', '', svg, flags=re.IGNORECASE)
    svg = re.sub(r'^\s*<!DOCTYPE[^>]*>\s*', '', svg, flags=re.IGNORECASE)
    svg = re.sub(r'[\r\n\t]+', ' ', svg)
    svg = re.sub(r'>\s+<', '><', svg)
    svg = re.sub(r'\s{2,}', ' ', svg)
    return svg.strip()


def replace_black_with_current_color(svg: str) -> str:
    black_pattern = r'(?:#000000|#000|black|rgb\(\s*0\s*,\s*0\s*,\s*0\s*\)|rgba\(\s*0\s*,\s*0\s*,\s*0\s*,\s*1(?:\.0+)?\s*\))'

    for attr in ("fill", "stroke"):
        svg = re.sub(
            rf'({attr}\s*=\s*")({black_pattern})(")',
            rf'\1currentColor\3',
            svg,
            flags=re.IGNORECASE,
        )
        svg = re.sub(
            rf"({attr}\s*=\s*')({black_pattern})(')",
            rf"\1currentColor\3",
            svg,
            flags=re.IGNORECASE,
        )

    svg = re.sub(rf'(?i)(fill\s*:\s*){black_pattern}', r'\1currentColor', svg)
    svg = re.sub(rf'(?i)(stroke\s*:\s*){black_pattern}', r'\1currentColor', svg)

    return svg


def add_or_replace_attr(attrs: str, name: str, value: str) -> str:
    pattern_dq = rf'\b{re.escape(name)}\s*=\s*"[^"]*"'
    pattern_sq = rf"\b{re.escape(name)}\s*=\s*'[^']*'"

    if re.search(pattern_dq, attrs, flags=re.IGNORECASE):
        return re.sub(pattern_dq, f'{name}="{value}"', attrs, count=1, flags=re.IGNORECASE)

    if re.search(pattern_sq, attrs, flags=re.IGNORECASE):
        return re.sub(pattern_sq, f'{name}="{value}"', attrs, count=1, flags=re.IGNORECASE)

    return attrs + f' {name}="{value}"'


def transform_svg_root(svg: str, tag_name: str) -> str:
    match = re.search(r'<svg\b([^>]*)>', svg, flags=re.IGNORECASE)
    if not match:
        raise ValueError(f"Nie znaleziono <svg> dla {tag_name}")

    attrs = match.group(1)

    attrs = re.sub(r'\swidth\s*=\s*"[^"]*"', '', attrs, flags=re.IGNORECASE)
    attrs = re.sub(r"\swidth\s*=\s*'[^']*'", '', attrs, flags=re.IGNORECASE)
    attrs = re.sub(r'\sheight\s*=\s*"[^"]*"', '', attrs, flags=re.IGNORECASE)
    attrs = re.sub(r"\sheight\s*=\s*'[^']*'", '', attrs, flags=re.IGNORECASE)

    attrs = add_or_replace_attr(attrs, "class", f"dice-inline dice-{tag_name.lower()}")
    attrs = add_or_replace_attr(
        attrs,
        "style",
        "display:inline-block;width:1.05em;height:1.05em;vertical-align:-0.12em;color:inherit;overflow:visible;"
    )
    attrs = add_or_replace_attr(attrs, "role", "img")
    attrs = add_or_replace_attr(attrs, "aria-label", tag_name)
    attrs = add_or_replace_attr(attrs, "focusable", "false")
    attrs = add_or_replace_attr(attrs, "preserveAspectRatio", "xMidYMid meet")
    attrs = add_or_replace_attr(attrs, "fill", "currentColor")
    attrs = add_or_replace_attr(attrs, "stroke", "currentColor")

    new_tag = f"<svg{attrs}>"
    return svg[:match.start()] + new_tag + svg[match.end():]


def canonicalize_tag(raw_tag: str) -> str | None:
    return ALIASES.get(raw_tag.lower())


def build_svg_symbol_html(tag_name: str, data_uri: str) -> str:
    svg = decode_data_uri_to_svg(data_uri)
    svg = normalize_svg(svg)
    svg = replace_black_with_current_color(svg)
    svg = transform_svg_root(svg, tag_name)
    return svg


def build_unicode_die_html(tag_name_lower: str) -> str:
    glyph, color, size = DICE_STYLES[tag_name_lower]
    return (
        f'<span title="{tag_name_lower}" '
        f'style="display:inline-block;line-height:1;vertical-align:-0.08em;'
        f'font-weight:700;color:{color};font-size:{size};">{glyph}</span>'
    )


def replace_tags(text: str, icon_map: dict[str, str]) -> str:
    def repl(match: re.Match[str]) -> str:
        raw_tag = match.group(1)
        canonical = canonicalize_tag(raw_tag)
        if not canonical:
            return match.group(0)

        lower = canonical.lower()

        if lower in DICE_STYLES:
            return build_unicode_die_html(lower)

        if canonical in SVG_SYMBOL_TAGS:
            data_uri = icon_map.get(canonical)
            if data_uri:
                return build_svg_symbol_html(canonical, data_uri)

        return match.group(0)

    return TAG_PATTERN.sub(repl, text)


def inject_style_block(text: str) -> str:
    if "<style>" in text and "dice-inline" in text:
        return text

    if text.startswith("---\n"):
        end = text.find("\n---", 4)

        if end != -1:
            end += len("\n---")
            return (
                text[:end]
                + "\n\n"
                + INJECTED_STYLE
                + "\n\n"
                + text[end:].lstrip()
            )

    return INJECTED_STYLE + "\n\n" + text


def main() -> None:
    if not CSS_SOURCE.exists():
        raise FileNotFoundError(f"Nie znaleziono pliku CSS: {CSS_SOURCE}")

    css_text = CSS_SOURCE.read_text(encoding="utf-8")
    icon_map = extract_icons_from_css(css_text)

    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    shutil.copytree(SRC_DIR, OUT_DIR)

    for path in OUT_DIR.rglob("*.md"):
        original = path.read_text(encoding="utf-8")
        updated = replace_tags(original, icon_map)
        updated = inject_style_block(updated)
        path.write_text(updated, encoding="utf-8")

    print(f"[OK] Zbudowano przetworzone markdowny w: {OUT_DIR}")


if __name__ == "__main__":
    main()
