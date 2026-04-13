# Changelog

## [0.2.0] - 2026-04-13

### Added
- **Persona Card** — 8-dimension stellar chart with persona label, insights, and PNG export
- **Xiaohongshu parser** — import your Little Red Book posts and comments
- **Spectrum Engine** — rule-based + LLM-scored personality dimensions (Night Owl, Reply Inertia, Expression Sharpness, Social Temperature Gap, Emotional Visibility, Content Omnivore, Taste Exclusivity, Cross-platform Contrast)
- **Selectable insights** — choose which insights appear on your card before exporting
- `/api/spectrum` endpoint for Web UI card data
- Evidence field in fragment API responses
- Import manifest with hash-based provenance tracking
- Behavioral fingerprint generation in analysis pipeline

### Changed
- Default LLM model updated to Claude Sonnet 4 (May 2025)
- Web UI fully localized to Chinese
- PersonaBench updated to v0.2

### Fixed
- WeChat parser type validation for CSV format detection
- Card canvas overflow clipping insights and footer
- Spectrum prompt template brace escaping

## [0.1.0] - 2026-04-06

Initial release.

- Core personality pipeline: extract → embed → store → synthesize
- Parsers: WeChat, YouTube, Bilibili, Telegram, WhatsApp
- CLI with import, chat, export, config commands
- Web UI with chat and import views
- PersonaBench v0.1 evaluation
- SOUL.md and core.md export
