# Percent — Brand & Logo Design Spec

## Decision Summary

- **Brand name:** Percent (previously Engram)
- **Logo:** % symbol reimagined — solid circle (you) + hollow circle (your reflection) + 3D bevel mirror line
- **Tagline EN:** "How much of you can AI understand?"
- **Tagline CN:** "你的数字痕迹，能还原百分之多少的你？"

## Why Percent

The name and logo are unified: the % symbol IS the logo. Hearing the name immediately conjures the visual, and seeing the logo immediately tells you the name. This level of name–logo unity is rare (Apple is the canonical example).

### Name strengths
- Universal recognition: every person on earth knows %
- Built-in product story: "what percentage of your personality can AI capture?"
- Curiosity gap: unexpected name for an AI personality tool → draws attention
- Works across languages and cultures

### Name tradeoffs
- Doesn't immediately say "AI personality mirror" without a tagline
- SEO for "percent" returns math results — mitigated by "Percent AI" or unique domain

## Logo Concept

Based on the user's original insight: the % symbol as `● / ○`

```
● = you (solid, real, the original)
/ = the mirror surface (3D bevel line with shadow)
○ = your reflection (hollow, the AI personality model)
```

### Logo structure
- `● / ○` arranged in standard % layout (upper-left solid, lower-right hollow, diagonal line)
- Solid circle: flat fill (#e8e4df dark / #1a1a1a light)
- Hollow circle: stroke only, same color
- Mirror line: 3D bevel effect (gradient + drop shadow) to suggest a reflective surface
- Two versions: dark-on-light (`logo-light.svg`) and light-on-dark (`logo.svg`)

### Design principles
- Monochrome first — color versions can be added later without changing the form
- Must be recognizable at favicon size (16px)
- The 3D effect is only on the line; circles remain flat

## What Changed

| File | Change |
|------|--------|
| `assets/logo.svg` | New % logo (dark background version) |
| `assets/logo-light.svg` | New % logo (light background version) |
| `README.md` | Engram → Percent, new tagline |
| `README_CN.md` | Engram → Percent, new Chinese tagline |

## What Did NOT Change

- Package name (`engram`) — CLI commands remain `engram` for now
- Python module structure — no code changes
- GitHub repo name — remains `looanli08-hl/engram`

These can be renamed in a separate task if desired.
