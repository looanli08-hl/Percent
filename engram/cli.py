"""Engram CLI — main entry point."""
from __future__ import annotations

import shutil
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(
    name="engram",
    help="Open-source personality modeling engine.",
    no_args_is_help=True,
)

import_app = typer.Typer(help="Import and analyze personal data.", no_args_is_help=True)
persona_app = typer.Typer(help="Manage the personality profile.", no_args_is_help=True)
export_app = typer.Typer(help="Export personality data.", no_args_is_help=True)
config_app = typer.Typer(help="Configure Engram settings.", no_args_is_help=True)

app.add_typer(import_app, name="import")
app.add_typer(persona_app, name="persona")
app.add_typer(export_app, name="export")
app.add_typer(config_app, name="config")

console = Console()

_PROMPTS_DIR = Path(__file__).parent.parent / "prompts"

# ── Supported parsers registry ───────────────────────────────────────────────

_PARSER_REGISTRY = {
    "bilibili": "engram.parsers.bilibili.BilibiliParser",
    "youtube": "engram.parsers.youtube.YouTubeParser",
    "wechat": "engram.parsers.wechat.WeChatParser",
}


def _get_parser(source: str):
    """Lazily import and return a parser instance for the given source name."""
    if source not in _PARSER_REGISTRY:
        console.print(f"[red]Unknown source '{source}'. Available: {', '.join(_PARSER_REGISTRY)}[/red]")
        raise typer.Exit(1)
    module_path, class_name = _PARSER_REGISTRY[source].rsplit(".", 1)
    import importlib
    module = importlib.import_module(module_path)
    return getattr(module, class_name)()


# ── engram init ──────────────────────────────────────────────────────────────

@app.command()
def init() -> None:
    """Create ~/.engram/ and configure API key."""
    from engram.config import EngramConfig, save_config

    engram_dir = Path.home() / ".engram"
    config = EngramConfig(engram_dir=engram_dir)

    if engram_dir.exists():
        console.print(f"[yellow]~/.engram/ already exists at {engram_dir}[/yellow]")
    else:
        engram_dir.mkdir(parents=True, exist_ok=True)
        (engram_dir / "raw").mkdir(exist_ok=True)
        console.print(f"[green]Created {engram_dir}[/green]")

    # Prompt for API key
    api_key = typer.prompt(
        "Enter your LLM API key (leave blank to skip)",
        default="",
        hide_input=True,
    )
    if api_key:
        config.llm_api_key = api_key

    # Prompt for provider
    provider = typer.prompt(
        "LLM provider [claude/openai/deepseek/ollama]",
        default=config.llm_provider,
    )
    config.llm_provider = provider

    save_config(config)
    console.print("[green]Configuration saved to ~/.engram/config.yaml[/green]")
    console.print("[bold]Engram is ready.[/bold]")


# ── engram import run ────────────────────────────────────────────────────────

@import_app.command("run")
def import_run(
    source: str = typer.Argument(..., help="Data source: bilibili, youtube, wechat"),
    path: Path = typer.Argument(..., help="Path to the exported data file or directory"),
) -> None:
    """Import and analyze data from a source."""
    from engram.config import load_config

    config = load_config()

    if not path.exists():
        console.print(f"[red]Path does not exist: {path}[/red]")
        raise typer.Exit(1)

    parser = _get_parser(source)

    if not parser.validate(path):
        console.print(f"[red]File/directory does not appear to be valid {source} data.[/red]")
        raise typer.Exit(1)

    with console.status(f"[bold]Parsing {source} data…[/bold]"):
        chunks = parser.parse(path)

    console.print(f"[green]Parsed {len(chunks)} chunks from {source}.[/green]")

    if not chunks:
        console.print("[yellow]No data found — nothing to import.[/yellow]")
        raise typer.Exit(0)

    if not config.llm_api_key:
        console.print("[yellow]Warning: no API key configured. Run 'engram init' first.[/yellow]")

    from engram.llm.client import LLMClient
    from engram.persona.engine import PersonaEngine

    client = LLMClient(
        provider=config.llm_provider,
        model=config.llm_model,
        api_key=config.llm_api_key,
    )
    engine = PersonaEngine(
        client=client,
        engram_dir=config.engram_dir,
        prompts_dir=_PROMPTS_DIR,
        embedding_model=config.embedding_model,
    )

    with console.status("[bold]Running persona analysis…[/bold]"):
        engine.run(chunks)

    console.print("[green]Import complete. core.md updated.[/green]")


# ── engram import guide ──────────────────────────────────────────────────────

@import_app.command("guide")
def import_guide(
    source: str = typer.Argument(..., help="Data source: bilibili, youtube, wechat"),
) -> None:
    """Show export instructions for a data source."""
    parser = _get_parser(source)
    console.print(parser.get_import_guide())


# ── engram import status ─────────────────────────────────────────────────────

@import_app.command("status")
def import_status() -> None:
    """Show fragment store statistics."""
    from engram.config import load_config
    from engram.persona.fragments import FragmentStore

    config = load_config()
    db_path = config.fragments_db_path

    if not db_path.exists():
        console.print("[yellow]No data imported yet. Run 'engram import run' first.[/yellow]")
        raise typer.Exit(0)

    store = FragmentStore(db_path)
    stats = store.stats()
    store.close()

    console.print(f"\n[bold]Fragment Store Stats[/bold]")
    console.print(f"  Total fragments: [cyan]{stats['total']}[/cyan]")

    if stats["by_source"]:
        table = Table(title="By Source", show_header=True, header_style="bold magenta")
        table.add_column("Source", style="cyan")
        table.add_column("Count", justify="right")
        for src, cnt in stats["by_source"].items():
            table.add_row(src, str(cnt))
        console.print(table)

    if stats["by_category"]:
        table = Table(title="By Category", show_header=True, header_style="bold magenta")
        table.add_column("Category", style="cyan")
        table.add_column("Count", justify="right")
        for cat, cnt in stats["by_category"].items():
            table.add_row(cat, str(cnt))
        console.print(table)


# ── engram persona view ──────────────────────────────────────────────────────

@persona_app.command("view")
def persona_view() -> None:
    """Print core.md personality profile."""
    from engram.config import load_config

    config = load_config()

    if not config.core_path.exists():
        console.print("[yellow]No personality profile yet. Run 'engram import run' first.[/yellow]")
        raise typer.Exit(0)

    content = config.core_path.read_text(encoding="utf-8")
    console.print(content)


# ── engram persona stats ─────────────────────────────────────────────────────

@persona_app.command("stats")
def persona_stats() -> None:
    """Show fragment statistics for the persona."""
    import_status()


# ── engram persona rebuild ───────────────────────────────────────────────────

@persona_app.command("rebuild")
def persona_rebuild() -> None:
    """Rebuild core.md from all stored fragments."""
    from engram.config import load_config
    from engram.llm.client import LLMClient
    from engram.persona.engine import PersonaEngine

    config = load_config()

    if not config.core_path.exists() and not config.fragments_db_path.exists():
        console.print("[yellow]No data found. Run 'engram import run' first.[/yellow]")
        raise typer.Exit(0)

    if not config.llm_api_key:
        console.print("[yellow]Warning: no API key configured. Run 'engram init' first.[/yellow]")

    client = LLMClient(
        provider=config.llm_provider,
        model=config.llm_model,
        api_key=config.llm_api_key,
    )
    engine = PersonaEngine(
        client=client,
        engram_dir=config.engram_dir,
        prompts_dir=_PROMPTS_DIR,
        embedding_model=config.embedding_model,
    )

    with console.status("[bold]Rebuilding core.md from fragments…[/bold]"):
        engine.rebuild_core()

    console.print("[green]core.md rebuilt successfully.[/green]")


# ── engram chat ──────────────────────────────────────────────────────────────

@app.command()
def chat(
    username: str = typer.Option("User", "--username", "-u", help="Your name used in the conversation."),
) -> None:
    """Start an interactive conversation with your Engram persona."""
    from engram.chat.engine import ChatEngine
    from engram.config import load_config

    config = load_config()

    if not config.core_path.exists():
        console.print("[yellow]No personality profile found. Run 'engram import run' first.[/yellow]")
        raise typer.Exit(0)

    if not config.llm_api_key:
        console.print("[yellow]Warning: no API key configured. Run 'engram init' first.[/yellow]")

    engine = ChatEngine(
        engram_dir=config.engram_dir,
        provider=config.llm_provider,
        model=config.llm_model,
        api_key=config.llm_api_key,
        prompts_dir=_PROMPTS_DIR,
        embedding_model=config.embedding_model,
        username=username,
    )

    console.print("[bold]Engram Chat[/bold] — type [italic]quit[/italic], [italic]exit[/italic], or [italic]q[/italic] to end.\n")

    while True:
        try:
            user_input = typer.prompt("You")
        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim]Goodbye.[/dim]")
            break

        if user_input.strip().lower() in {"quit", "exit", "q"}:
            console.print("[dim]Goodbye.[/dim]")
            break

        with console.status("[dim]Thinking…[/dim]"):
            response = engine.send(user_input)

        console.print(f"[bold cyan]Engram:[/bold cyan] {response}\n")


# ── engram export soul ───────────────────────────────────────────────────────

@export_app.command("soul")
def export_soul(
    output: Path = typer.Option(Path("SOUL.md"), "--output", "-o", help="Output path for SOUL.md"),
) -> None:
    """Generate SOUL.md from core.md."""
    from engram.config import load_config
    from engram.export.soul_md import SoulMdExporter

    config = load_config()

    if not config.core_path.exists():
        console.print("[yellow]No personality profile found. Run 'engram import run' first.[/yellow]")
        raise typer.Exit(0)

    if not config.llm_api_key:
        console.print("[yellow]Warning: no API key configured. Run 'engram init' first.[/yellow]")

    exporter = SoulMdExporter(
        provider=config.llm_provider,
        model=config.llm_model,
        api_key=config.llm_api_key,
        prompts_dir=_PROMPTS_DIR,
    )

    with console.status("[bold]Generating SOUL.md…[/bold]"):
        exporter.export(config.core_path, output)

    console.print(f"[green]SOUL.md written to {output}[/green]")


# ── engram export core ───────────────────────────────────────────────────────

@export_app.command("core")
def export_core(
    output: Path = typer.Option(Path("core.md"), "--output", "-o", help="Destination path for core.md"),
) -> None:
    """Copy core.md to the specified path."""
    from engram.config import load_config

    config = load_config()

    if not config.core_path.exists():
        console.print("[yellow]No personality profile found. Run 'engram import run' first.[/yellow]")
        raise typer.Exit(0)

    shutil.copy2(config.core_path, output)
    console.print(f"[green]core.md copied to {output}[/green]")


# ── engram config llm ────────────────────────────────────────────────────────

@config_app.command("llm")
def config_llm() -> None:
    """Configure the LLM provider and model."""
    from engram.config import load_config, save_config

    config = load_config()

    console.print(f"Current provider: [cyan]{config.llm_provider}[/cyan]")
    console.print(f"Current model:    [cyan]{config.llm_model}[/cyan]")
    console.print(f"API key set:      [cyan]{'yes' if config.llm_api_key else 'no'}[/cyan]\n")

    provider = typer.prompt(
        "LLM provider [claude/openai/deepseek/ollama]",
        default=config.llm_provider,
    )
    model = typer.prompt("Model name", default=config.llm_model)
    api_key = typer.prompt(
        "API key (leave blank to keep current)",
        default="",
        hide_input=True,
    )

    config.llm_provider = provider
    config.llm_model = model
    if api_key:
        config.llm_api_key = api_key

    save_config(config)
    console.print("[green]LLM configuration saved.[/green]")


# ── engram config parsers ────────────────────────────────────────────────────

@config_app.command("parsers")
def config_parsers() -> None:
    """List available data parsers."""
    table = Table(title="Available Parsers", show_header=True, header_style="bold magenta")
    table.add_column("Source", style="cyan")
    table.add_column("Description")

    for source, dotted_path in _PARSER_REGISTRY.items():
        # Lazily get description from parser class without loading heavy deps
        try:
            parser = _get_parser(source)
            description = getattr(parser, "description", "—")
        except Exception:
            description = dotted_path
        table.add_row(source, description)

    console.print(table)
