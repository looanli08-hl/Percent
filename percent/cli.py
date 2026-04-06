"""Percent CLI — main entry point."""

from __future__ import annotations

import shutil
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(
    name="percent",
    help="Open-source personality modeling engine.",
    no_args_is_help=True,
)

import_app = typer.Typer(help="Import and analyze personal data.", no_args_is_help=True)
persona_app = typer.Typer(help="Manage the personality profile.", no_args_is_help=True)
export_app = typer.Typer(help="Export personality data.", no_args_is_help=True)
config_app = typer.Typer(help="Configure Percent settings.", no_args_is_help=True)

app.add_typer(import_app, name="import")
app.add_typer(persona_app, name="persona")
app.add_typer(export_app, name="export")
app.add_typer(config_app, name="config")

console = Console()

_PROMPTS_DIR = Path(__file__).parent.parent / "prompts"
_NO_PROFILE_MSG = "[yellow]No personality profile found. Run 'percent import run' first.[/yellow]"

# ── Supported parsers registry ───────────────────────────────────────────────

_PARSER_REGISTRY = {
    "bilibili": "percent.parsers.bilibili.BilibiliParser",
    "youtube": "percent.parsers.youtube.YouTubeParser",
    "wechat": "percent.parsers.wechat.WeChatParser",
}


def _get_parser(source: str):
    """Lazily import and return a parser instance for the given source name."""
    if source not in _PARSER_REGISTRY:
        available = ", ".join(_PARSER_REGISTRY)
        console.print(f"[red]Unknown source '{source}'. Available: {available}[/red]")
        raise typer.Exit(1)
    module_path, class_name = _PARSER_REGISTRY[source].rsplit(".", 1)
    import importlib

    module = importlib.import_module(module_path)
    return getattr(module, class_name)()


# ── percent init ──────────────────────────────────────────────────────────────


@app.command()
def init() -> None:
    """Create ~/.percent/ and configure API key."""
    from percent.config import PercentConfig, save_config

    percent_dir = Path.home() / ".percent"
    config = PercentConfig(percent_dir=percent_dir)

    if percent_dir.exists():
        console.print(f"[yellow]~/.percent/ already exists at {percent_dir}[/yellow]")
    else:
        percent_dir.mkdir(parents=True, exist_ok=True)
        (percent_dir / "raw").mkdir(exist_ok=True)
        console.print(f"[green]Created {percent_dir}[/green]")

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
    console.print("[green]Configuration saved to ~/.percent/config.yaml[/green]")
    console.print("[bold]Percent is ready.[/bold]")


# ── percent import run ────────────────────────────────────────────────────────


@import_app.command("run")
def import_run(
    source: str = typer.Argument(..., help="Data source: bilibili, youtube, wechat"),
    path: Path = typer.Argument(..., help="Path to the exported data file or directory"),
) -> None:
    """Import and analyze data from a source."""
    from percent.config import load_config

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
        console.print("[yellow]Warning: no API key configured. Run 'percent init' first.[/yellow]")

    from percent.llm.client import LLMClient
    from percent.persona.engine import PersonaEngine

    client = LLMClient(
        provider=config.llm_provider,
        model=config.llm_model,
        api_key=config.llm_api_key,
    )
    engine = PersonaEngine(
        client=client,
        percent_dir=config.percent_dir,
        prompts_dir=_PROMPTS_DIR,
        embedding_model=config.embedding_model,
    )

    with console.status("[bold]Running persona analysis…[/bold]"):
        engine.run(chunks)

    console.print("[green]Import complete. core.md updated.[/green]")


# ── percent import bilibili ───────────────────────────────────────────────────


@import_app.command("bilibili")
def import_bilibili_auto(
    cookie: str = typer.Option(..., "--cookie", "-c", help="Your Bilibili cookie string"),
    max_pages: int = typer.Option(50, "--max-pages", help="Maximum pages to fetch"),
) -> None:
    """Import Bilibili watch history directly via API (no manual export needed)."""
    from percent.config import load_config
    from percent.parsers.bilibili_api import fetch_bilibili_history

    config = load_config()
    if not config.llm_api_key:
        console.print("[red]No API key configured. Run 'percent init' first.[/red]")
        raise typer.Exit(1)

    console.print("[cyan]Fetching Bilibili watch history via API...[/cyan]")
    try:
        chunks = fetch_bilibili_history(cookie, max_pages=max_pages)
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)

    if not chunks:
        console.print("[yellow]No watch history found. Check your cookie.[/yellow]")
        raise typer.Exit(0)

    console.print(f"[cyan]Fetched {len(chunks)} videos. Running personality analysis...[/cyan]")

    from percent.llm.client import LLMClient
    from percent.persona.engine import PersonaEngine

    client = LLMClient(
        provider=config.llm_provider,
        model=config.llm_model,
        api_key=config.llm_api_key,
    )
    engine = PersonaEngine(
        client=client,
        percent_dir=config.percent_dir,
        prompts_dir=_PROMPTS_DIR,
        embedding_model=config.embedding_model,
    )

    with console.status("[bold cyan]Analyzing personality...[/bold cyan]"):
        engine.run(chunks)

    console.print("\n[green]Analysis complete![/green]")
    console.print(f"  Videos analyzed: {len(chunks)}")
    console.print(f"  Core profile: {config.core_path}")


# ── percent import guide ──────────────────────────────────────────────────────


@import_app.command("guide")
def import_guide(
    source: str = typer.Argument(..., help="Data source: bilibili, youtube, wechat"),
) -> None:
    """Show export instructions for a data source."""
    parser = _get_parser(source)
    console.print(parser.get_import_guide())


# ── percent import status ─────────────────────────────────────────────────────


@import_app.command("status")
def import_status() -> None:
    """Show fragment store statistics."""
    from percent.config import load_config
    from percent.persona.fragments import FragmentStore

    config = load_config()
    db_path = config.fragments_db_path

    if not db_path.exists():
        console.print("[yellow]No data imported yet. Run 'percent import run' first.[/yellow]")
        raise typer.Exit(0)

    store = FragmentStore(db_path)
    stats = store.stats()
    store.close()

    console.print("\n[bold]Fragment Store Stats[/bold]")
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


# ── percent persona view ──────────────────────────────────────────────────────


@persona_app.command("view")
def persona_view() -> None:
    """Print core.md personality profile."""
    from percent.config import load_config

    config = load_config()

    if not config.core_path.exists():
        console.print("[yellow]No personality profile yet. Run 'percent import run' first.[/yellow]")
        raise typer.Exit(0)

    content = config.core_path.read_text(encoding="utf-8")
    console.print(content)


# ── percent persona stats ─────────────────────────────────────────────────────


@persona_app.command("stats")
def persona_stats() -> None:
    """Show fragment statistics for the persona."""
    import_status()


# ── percent persona rebuild ───────────────────────────────────────────────────


@persona_app.command("rebuild")
def persona_rebuild() -> None:
    """Rebuild core.md from all stored fragments."""
    from percent.config import load_config
    from percent.llm.client import LLMClient
    from percent.persona.engine import PersonaEngine

    config = load_config()

    if not config.core_path.exists() and not config.fragments_db_path.exists():
        console.print("[yellow]No data found. Run 'percent import run' first.[/yellow]")
        raise typer.Exit(0)

    if not config.llm_api_key:
        console.print("[yellow]Warning: no API key configured. Run 'percent init' first.[/yellow]")

    client = LLMClient(
        provider=config.llm_provider,
        model=config.llm_model,
        api_key=config.llm_api_key,
    )
    engine = PersonaEngine(
        client=client,
        percent_dir=config.percent_dir,
        prompts_dir=_PROMPTS_DIR,
        embedding_model=config.embedding_model,
    )

    with console.status("[bold]Rebuilding core.md from fragments…[/bold]"):
        engine.rebuild_core()

    console.print("[green]core.md rebuilt successfully.[/green]")


# ── percent persona deep-analyze ──────────────────────────────────────────────


@persona_app.command("deep-analyze")
def persona_deep_analyze() -> None:
    """Run cross-validation + deep analysis to improve personality model."""
    from percent.config import load_config
    from percent.llm.client import LLMClient
    from percent.persona.engine import PersonaEngine

    config = load_config()

    if not config.fragments_db_path.exists():
        console.print("[yellow]No data found. Run 'percent import run' first.[/yellow]")
        raise typer.Exit(0)

    if not config.llm_api_key:
        console.print("[yellow]Warning: no API key configured. Run 'percent init' first.[/yellow]")

    client = LLMClient(
        provider=config.llm_provider,
        model=config.llm_model,
        api_key=config.llm_api_key,
    )
    engine = PersonaEngine(
        client=client,
        percent_dir=config.percent_dir,
        prompts_dir=_PROMPTS_DIR,
        embedding_model=config.embedding_model,
    )

    console.print("[bold]Phase 1:[/bold] Cross-source validation…")
    console.print("[bold]Phase 2:[/bold] Deep pattern analysis…")
    console.print("[bold]Phase 3:[/bold] Re-synthesizing core.md…")

    with console.status("[bold]Running deep analysis…[/bold]"):
        core_md = engine.deep_analyze()

    if not core_md:
        console.print("[yellow]No fragments to analyze.[/yellow]")
        raise typer.Exit(0)

    stats = engine.stats()
    console.print(f"\n[green]Deep analysis complete.[/green]")
    console.print(f"Total fragments: {stats['total']} (including deep analysis findings)")
    console.print(f"Updated core.md with deeper insights.")


# ── percent persona big-five ──────────────────────────────────────────────────


@persona_app.command("big-five")
def persona_big_five() -> None:
    """Compute Big Five personality scores from your profile."""
    from percent.config import load_config
    from percent.llm.client import LLMClient
    from percent.persona.big_five import compute_big_five, save_big_five

    config = load_config()

    if not config.core_path.exists():
        console.print(_NO_PROFILE_MSG)
        raise typer.Exit(0)

    if not config.llm_api_key:
        console.print("[yellow]Warning: no API key configured. Run 'percent init' first.[/yellow]")

    core_md = config.core_path.read_text(encoding="utf-8")

    client = LLMClient(
        provider=config.llm_provider,
        model=config.llm_model,
        api_key=config.llm_api_key,
    )

    with console.status("[bold]Computing Big Five personality scores…[/bold]"):
        result = compute_big_five(client, core_md, prompts_dir=_PROMPTS_DIR)

    big_five_path = config.percent_dir / "big_five.json"
    save_big_five(result, big_five_path)

    console.print()
    console.print(result.format_report())
    console.print(f"[green]Saved to {big_five_path}[/green]")


# ── percent persona validate ──────────────────────────────────────────────────


@persona_app.command("validate")
def persona_validate(
    num_tests: int = typer.Option(10, help="Number of fragments to use as test cases."),
) -> None:
    """Run PersonaBench — measure personality model accuracy."""
    from percent.config import load_config
    from percent.llm.client import LLMClient
    from percent.persona.bench import PersonaBench
    from percent.persona.fragments import FragmentStore
    from percent.persona.validator import PersonaValidator

    config = load_config()

    if not config.core_path.exists():
        console.print(_NO_PROFILE_MSG)
        raise typer.Exit(0)

    if not config.llm_api_key:
        console.print("[yellow]Warning: no API key configured. Run 'percent init' first.[/yellow]")

    core_md = config.core_path.read_text(encoding="utf-8")

    store = FragmentStore(config.fragments_db_path)
    fragments = store.get_all()
    store.close()

    if not fragments:
        console.print("[yellow]No fragments found. Run 'percent import run' first.[/yellow]")
        raise typer.Exit(0)

    from datetime import datetime

    from percent.models import ChunkType, DataChunk

    test_chunks = [
        DataChunk(
            source=f.source,
            type=ChunkType.CONVERSATION,
            timestamp=datetime.now(),
            content=f.content,
        )
        for f in fragments
    ]

    client = LLMClient(
        provider=config.llm_provider,
        model=config.llm_model,
        api_key=config.llm_api_key,
    )
    validator = PersonaValidator(client, prompts_dir=_PROMPTS_DIR)
    bench = PersonaBench(validator)

    with console.status("[bold]Running PersonaBench…[/bold]"):
        result = bench.evaluate(core_md, test_chunks, num_tests=num_tests)

    console.print(bench.format_report(result))


# ── percent chat ──────────────────────────────────────────────────────────────


@app.command()
def chat(
    username: str = typer.Option("User", "--username", "-u", help="Your name in the conversation."),
) -> None:
    """Start an interactive conversation with your Percent persona."""
    from percent.chat.engine import ChatEngine
    from percent.config import load_config

    config = load_config()

    if not config.core_path.exists():
        console.print(_NO_PROFILE_MSG)
        raise typer.Exit(0)

    if not config.llm_api_key:
        console.print("[yellow]Warning: no API key configured. Run 'percent init' first.[/yellow]")

    engine = ChatEngine(
        percent_dir=config.percent_dir,
        provider=config.llm_provider,
        model=config.llm_model,
        api_key=config.llm_api_key,
        prompts_dir=_PROMPTS_DIR,
        embedding_model=config.embedding_model,
        username=username,
    )

    console.print(
        "[bold]Percent Chat[/bold] — type [italic]quit[/italic], "
        "[italic]exit[/italic], or [italic]q[/italic] to end.\n"
    )

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

        console.print(f"[bold cyan]Percent:[/bold cyan] {response}\n")


# ── percent web ───────────────────────────────────────────────────────────────


@app.command()
def web(
    port: int = typer.Option(18900, help="Port to run the web UI on."),
) -> None:
    """Launch Percent Web UI in your browser."""
    import threading
    import webbrowser

    from percent.web import start_server

    url = f"http://localhost:{port}"
    console.print(f"[cyan]Starting Percent Web UI at {url}[/cyan]")
    threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    start_server(port=port)


# ── percent export soul ───────────────────────────────────────────────────────


@export_app.command("soul")
def export_soul(
    output: Path = typer.Option(Path("SOUL.md"), "--output", "-o", help="Output path for SOUL.md"),
) -> None:
    """Generate SOUL.md from core.md."""
    from percent.config import load_config
    from percent.export.soul_md import SoulMdExporter

    config = load_config()

    if not config.core_path.exists():
        console.print(_NO_PROFILE_MSG)
        raise typer.Exit(0)

    if not config.llm_api_key:
        console.print("[yellow]Warning: no API key configured. Run 'percent init' first.[/yellow]")

    exporter = SoulMdExporter(
        provider=config.llm_provider,
        model=config.llm_model,
        api_key=config.llm_api_key,
        prompts_dir=_PROMPTS_DIR,
    )

    with console.status("[bold]Generating SOUL.md…[/bold]"):
        exporter.export(config.core_path, output)

    console.print(f"[green]SOUL.md written to {output}[/green]")


# ── percent export core ───────────────────────────────────────────────────────


@export_app.command("core")
def export_core(
    output: Path = typer.Option(Path("core.md"), "--output", "-o", help="Destination path."),
) -> None:
    """Copy core.md to the specified path."""
    from percent.config import load_config

    config = load_config()

    if not config.core_path.exists():
        console.print(_NO_PROFILE_MSG)
        raise typer.Exit(0)

    shutil.copy2(config.core_path, output)
    console.print(f"[green]core.md copied to {output}[/green]")


# ── percent config llm ────────────────────────────────────────────────────────


@config_app.command("llm")
def config_llm() -> None:
    """Configure the LLM provider and model."""
    from percent.config import load_config, save_config

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


# ── percent config parsers ────────────────────────────────────────────────────


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
