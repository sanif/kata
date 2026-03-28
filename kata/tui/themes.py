"""Custom themes for Kata TUI."""

from textual.theme import Theme

# ──────────────────────────────────────────────
# Kata Dark — the default
# Deep indigo with teal accent, refined elevation
# ──────────────────────────────────────────────
KATA_DARK = Theme(
    name="kata-dark",
    primary="#22d3ee",  # Cyan-400
    secondary="#a78bfa",  # Violet-400
    warning="#fbbf24",  # Amber-400
    error="#f87171",  # Red-400
    success="#4ade80",  # Green-400
    accent="#f472b6",  # Pink-400
    foreground="#e2e8f0",  # Slate-200
    background="#0f172a",  # Slate-900
    surface="#162033",  # Subtle step from bg
    panel="#1e2a3e",  # Card/modal distinction
    dark=True,
    luminosity_spread=0.15,
    text_alpha=0.95,
)

# ──────────────────────────────────────────────
# Kata Light — clean, minimal
# ──────────────────────────────────────────────
KATA_LIGHT = Theme(
    name="kata-light",
    primary="#0891b2",  # Cyan-600
    secondary="#7c3aed",  # Violet-600
    warning="#d97706",  # Amber-600
    error="#dc2626",  # Red-600
    success="#16a34a",  # Green-600
    accent="#db2777",  # Pink-600
    foreground="#1e293b",  # Slate-800
    background="#f8fafc",  # Slate-50
    surface="#f1f5f9",  # Slate-100
    panel="#e2e8f0",  # Slate-200
    dark=False,
    luminosity_spread=0.15,
    text_alpha=0.87,
)

# ──────────────────────────────────────────────
# Kata Ocean — deep blues, dramatic
# ──────────────────────────────────────────────
KATA_OCEAN = Theme(
    name="kata-ocean",
    primary="#38bdf8",  # Sky-400
    secondary="#c084fc",  # Purple-400
    warning="#fb923c",  # Orange-400
    error="#f87171",  # Red-400
    success="#34d399",  # Emerald-400
    accent="#2dd4bf",  # Teal-400
    foreground="#e0f2fe",  # Sky-100
    background="#0c1222",  # Very dark blue
    surface="#162032",  # Dark blue
    panel="#1e3a5f",  # Medium dark blue
    dark=True,
    luminosity_spread=0.18,
    text_alpha=0.95,
)

# ──────────────────────────────────────────────
# Kata Warm — paper-like, warm
# ──────────────────────────────────────────────
KATA_WARM = Theme(
    name="kata-warm",
    primary="#ea580c",  # Orange-600
    secondary="#4f46e5",  # Indigo-600
    warning="#ca8a04",  # Yellow-600
    error="#dc2626",  # Red-600
    success="#059669",  # Emerald-600
    accent="#be185d",  # Pink-700
    foreground="#292524",  # Stone-800
    background="#faf7f5",  # Warm white
    surface="#f5f0eb",  # Warm gray
    panel="#e7e0d8",  # Warmer gray
    dark=False,
    luminosity_spread=0.12,
    text_alpha=0.90,
)

# ──────────────────────────────────────────────
# Kata Glass — frosted dark, muted tones
# ──────────────────────────────────────────────
KATA_GLASS = Theme(
    name="kata-glass",
    primary="#7dd3fc",  # Sky-300
    secondary="#c4b5fd",  # Violet-300
    warning="#fcd34d",  # Amber-300
    error="#fca5a5",  # Red-300
    success="#86efac",  # Green-300
    accent="#f9a8d4",  # Pink-300
    foreground="#f1f5f9",  # Slate-100
    background="#1a1f2e",  # Muted blue-gray
    surface="#232a3e",  # Glass layer 1
    panel="#2d3550",  # Glass layer 2
    dark=True,
    luminosity_spread=0.15,
    text_alpha=0.92,
)

# ──────────────────────────────────────────────
# Kata Glass Light — frosted white, soft
# ──────────────────────────────────────────────
KATA_GLASS_LIGHT = Theme(
    name="kata-glass-light",
    primary="#0ea5e9",  # Sky-500
    secondary="#8b5cf6",  # Violet-500
    warning="#f59e0b",  # Amber-500
    error="#ef4444",  # Red-500
    success="#22c55e",  # Green-500
    accent="#ec4899",  # Pink-500
    foreground="#334155",  # Slate-700
    background="#f8fafc",  # Slate-50
    surface="#f1f5f9",  # Slate-100
    panel="#e2e8f0",  # Slate-200
    dark=False,
    luminosity_spread=0.08,
    text_alpha=0.88,
)

# ──────────────────────────────────────────────
# Kata Rose — dark with muted rose accent
# Inspired by Rose Pine — soft, warm, contemplative
# ──────────────────────────────────────────────
KATA_ROSE = Theme(
    name="kata-rose",
    primary="#ebbcba",  # Rose — muted pink
    secondary="#c4a7e7",  # Iris — soft purple
    warning="#f6c177",  # Gold
    error="#eb6f92",  # Love — hot pink
    success="#9ccfd8",  # Foam — soft cyan
    accent="#c4a7e7",  # Iris
    foreground="#e0def4",  # Soft lavender text
    background="#191724",  # Deep purple-black
    surface="#1f1d2e",  # Purple surface
    panel="#26233a",  # Purple overlay
    dark=True,
    luminosity_spread=0.15,
    text_alpha=0.92,
)

# ──────────────────────────────────────────────
# Kata Nord — arctic, muted, disciplined
# Inspired by Nord palette — cool and calm
# ──────────────────────────────────────────────
KATA_NORD = Theme(
    name="kata-nord",
    primary="#88c0d0",  # Frost teal
    secondary="#b48ead",  # Aurora purple
    warning="#ebcb8b",  # Aurora yellow
    error="#bf616a",  # Aurora red
    success="#a3be8c",  # Aurora green
    accent="#81a1c1",  # Frost blue
    foreground="#eceff4",  # Snow storm
    background="#2e3440",  # Polar night 0
    surface="#3b4252",  # Polar night 1
    panel="#434c5e",  # Polar night 2
    dark=True,
    luminosity_spread=0.12,
    text_alpha=0.95,
)

# ──────────────────────────────────────────────
# Kata Mono — no hue, pure luminance
# For the terminal purist — brightness is the only variable
# ──────────────────────────────────────────────
KATA_MONO = Theme(
    name="kata-mono",
    primary="#a0a0a0",  # Mid gray accent
    secondary="#707070",  # Darker gray
    warning="#c8c8c8",  # Light gray
    error="#ffffff",  # Pure white — demands attention
    success="#888888",  # Medium gray
    accent="#606060",  # Subtle gray
    foreground="#d0d0d0",  # Light gray text
    background="#111111",  # Near black
    surface="#1a1a1a",  # Dark gray
    panel="#232323",  # Medium dark gray
    dark=True,
    luminosity_spread=0.08,
    text_alpha=0.90,
)

# ──────────────────────────────────────────────
# Kata Ember — dark with warm amber accent
# Campfire glow — warm, focused, intimate
# ──────────────────────────────────────────────
KATA_EMBER = Theme(
    name="kata-ember",
    primary="#f59e0b",  # Amber-500 — warm gold
    secondary="#a78bfa",  # Violet-400
    warning="#fb923c",  # Orange-400
    error="#ef4444",  # Red-500
    success="#4ade80",  # Green-400
    accent="#f97316",  # Orange-500
    foreground="#e8ddd4",  # Warm light
    background="#1a1210",  # Very dark warm brown
    surface="#231a15",  # Dark brown
    panel="#2d221b",  # Medium brown
    dark=True,
    luminosity_spread=0.18,
    text_alpha=0.93,
)

# All Kata themes
KATA_THEMES = [
    KATA_DARK,
    KATA_LIGHT,
    KATA_OCEAN,
    KATA_WARM,
    KATA_GLASS,
    KATA_GLASS_LIGHT,
    KATA_ROSE,
    KATA_NORD,
    KATA_MONO,
    KATA_EMBER,
]
