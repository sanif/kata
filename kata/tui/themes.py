"""Custom themes for Kata TUI."""

from textual.theme import Theme

# Kata Dark Theme
# Inspired by Japanese aesthetics - deep indigo with teal accents
KATA_DARK = Theme(
    name="kata-dark",
    primary="#22d3ee",      # Cyan-400 - bright teal accent
    secondary="#a78bfa",    # Violet-400 - purple secondary
    warning="#fbbf24",      # Amber-400
    error="#f87171",        # Red-400
    success="#4ade80",      # Green-400
    accent="#f472b6",       # Pink-400
    foreground="#e2e8f0",   # Slate-200
    background="#0f172a",   # Slate-900 - deep blue-black
    surface="#1e293b",      # Slate-800
    panel="#334155",        # Slate-700
    dark=True,
    luminosity_spread=0.15,
    text_alpha=0.95,
)

# Kata Light Theme
# Clean, minimal light theme with the same accent colors
KATA_LIGHT = Theme(
    name="kata-light",
    primary="#0891b2",      # Cyan-600 - deeper teal for light bg
    secondary="#7c3aed",    # Violet-600
    warning="#d97706",      # Amber-600
    error="#dc2626",        # Red-600
    success="#16a34a",      # Green-600
    accent="#db2777",       # Pink-600
    foreground="#1e293b",   # Slate-800
    background="#f8fafc",   # Slate-50 - almost white
    surface="#f1f5f9",      # Slate-100
    panel="#e2e8f0",        # Slate-200
    dark=False,
    luminosity_spread=0.15,
    text_alpha=0.87,
)

# Kata Ocean Theme (Alternative Dark)
# Deeper blues, more dramatic
KATA_OCEAN = Theme(
    name="kata-ocean",
    primary="#38bdf8",      # Sky-400 - bright blue
    secondary="#c084fc",    # Purple-400
    warning="#fb923c",      # Orange-400
    error="#f87171",        # Red-400
    success="#34d399",      # Emerald-400
    accent="#2dd4bf",       # Teal-400
    foreground="#e0f2fe",   # Sky-100
    background="#0c1222",   # Very dark blue
    surface="#162032",      # Dark blue
    panel="#1e3a5f",        # Medium dark blue
    dark=True,
    luminosity_spread=0.18,
    text_alpha=0.95,
)

# Kata Warm Theme (Alternative Light)
# Warm, paper-like feel
KATA_WARM = Theme(
    name="kata-warm",
    primary="#ea580c",      # Orange-600 - warm orange
    secondary="#4f46e5",    # Indigo-600
    warning="#ca8a04",      # Yellow-600
    error="#dc2626",        # Red-600
    success="#059669",      # Emerald-600
    accent="#be185d",       # Pink-700
    foreground="#292524",   # Stone-800
    background="#faf7f5",   # Warm white
    surface="#f5f0eb",      # Warm gray
    panel="#e7e0d8",        # Warmer gray
    dark=False,
    luminosity_spread=0.12,
    text_alpha=0.90,
)

# Kata Glass Theme (Dark)
# Frosted glass aesthetic - muted, translucent-looking colors
KATA_GLASS = Theme(
    name="kata-glass",
    primary="#7dd3fc",      # Sky-300 - soft cyan
    secondary="#c4b5fd",    # Violet-300 - soft purple
    warning="#fcd34d",      # Amber-300
    error="#fca5a5",        # Red-300
    success="#86efac",      # Green-300
    accent="#f9a8d4",       # Pink-300
    foreground="#f1f5f9",   # Slate-100 - bright text
    background="#1a1f2e",   # Muted dark blue-gray (frosted dark)
    surface="#252b3b",      # Slightly lighter (glass layer 1)
    panel="#303847",        # Glass layer 2
    dark=True,
    luminosity_spread=0.10,  # Low spread for subtle transitions
    text_alpha=0.92,
)

# Kata Glass Light Theme
# Light frosted glass - soft whites and silvers
KATA_GLASS_LIGHT = Theme(
    name="kata-glass-light",
    primary="#0ea5e9",      # Sky-500 - clean blue
    secondary="#8b5cf6",    # Violet-500
    warning="#f59e0b",      # Amber-500
    error="#ef4444",        # Red-500
    success="#22c55e",      # Green-500
    accent="#ec4899",       # Pink-500
    foreground="#334155",   # Slate-700 - readable dark text
    background="#f8fafc",   # Slate-50 - frosted white
    surface="#f1f5f9",      # Slate-100 - glass layer 1
    panel="#e2e8f0",        # Slate-200 - glass layer 2
    dark=False,
    luminosity_spread=0.08,  # Very subtle transitions
    text_alpha=0.88,
)

# All Kata themes
KATA_THEMES = [KATA_DARK, KATA_LIGHT, KATA_OCEAN, KATA_WARM, KATA_GLASS, KATA_GLASS_LIGHT]
