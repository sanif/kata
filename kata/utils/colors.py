"""Color presets and utilities for per-project color indicators."""

COLOR_PRESETS: dict[str, str] = {
    "blue": "#5B9BD5",
    "red": "#E06C75",
    "green": "#98C379",
    "orange": "#D19A66",
    "purple": "#C678DD",
    "teal": "#56B6C2",
    "rose": "#E06C96",
    "amber": "#E5C07B",
    "cyan": "#61AFEF",
    "lime": "#B5E550",
    "coral": "#FF7F50",
    "slate": "#ABB2BF",
}


def resolve_color(color: str | None) -> str | None:
    """Resolve a named preset or hex code to a hex value."""
    if color is None:
        return None
    if color.startswith("#"):
        return color
    return COLOR_PRESETS.get(color.lower())


def hex_to_256(hex_color: str) -> int:
    """Convert hex color to nearest xterm-256 color index."""
    r = int(hex_color[1:3], 16)
    g = int(hex_color[3:5], 16)
    b = int(hex_color[5:7], 16)

    gray = round(0.299 * r + 0.587 * g + 0.114 * b)
    if r == g == b or (abs(r - g) < 10 and abs(g - b) < 10 and abs(r - b) < 10):
        if gray < 4:
            return 16
        if gray > 238:
            return 231
        return 232 + round((gray - 8) / 10)

    r_idx = round(r / 255 * 5)
    g_idx = round(g / 255 * 5)
    b_idx = round(b / 255 * 5)
    return 16 + 36 * r_idx + 6 * g_idx + b_idx
