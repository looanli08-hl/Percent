"""Percent Web UI — FastAPI server with chat interface and persona viewer."""

from __future__ import annotations

from pathlib import Path

import uvicorn
from fastapi import FastAPI, Form, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from percent.config import PercentConfig, load_config
from percent.persona.fragments import FragmentStore
from percent.persona.spectrum import generate_card_data, CardData

app = FastAPI(title="Percent", description="Open-source personality modeling engine")

# Global state (initialized on startup)
_chat_engine = None
_config: PercentConfig | None = None


def _require_config() -> PercentConfig:
    """Return config or raise if not initialized."""
    if _config is None:
        raise RuntimeError("Server not initialized")
    return _config

_PROMPTS_DIR = Path(__file__).parent / "prompts"
_STATIC_DIR = Path(__file__).parent / "static"


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    response: str


@app.on_event("startup")
def startup() -> None:
    global _chat_engine, _config
    _config = load_config()

    # Only initialize ChatEngine if core.md exists (requires persona to be built)
    if _config.core_path.exists():
        from percent.chat.engine import ChatEngine

        _chat_engine = ChatEngine(
            percent_dir=_config.percent_dir,
            provider=_config.llm_provider,
            model=_config.llm_model,
            api_key=_config.llm_api_key,
            prompts_dir=_PROMPTS_DIR,
            embedding_model=_config.embedding_model,
        )


@app.get("/api/persona")
def get_persona() -> dict:
    """Return core.md content as JSON."""
    cfg = _require_config()
    core_path = cfg.core_path
    if core_path.exists():
        return {"content": core_path.read_text(encoding="utf-8")}
    return {"content": "No personality profile yet. Run `percent import run` first."}


@app.get("/api/stats")
def get_stats() -> dict:
    """Return fragment statistics."""
    db_path = _require_config().fragments_db_path
    if not db_path.exists():
        return {"total": 0, "by_source": {}, "by_category": {}}
    store = FragmentStore(db_path)
    stats = store.stats()
    store.close()
    return stats


@app.get("/api/insights")
def get_insights() -> dict:
    """Return cross-source validated insights with evidence."""
    db_path = _require_config().fragments_db_path
    if not db_path.exists():
        return {"insights": []}
    store = FragmentStore(db_path)
    insights = store.get_cross_source_insights()
    store.close()
    return {"insights": insights}


@app.get("/api/spectrum")
def get_spectrum(regenerate: bool = False) -> dict:
    """Return persona spectrum. Cached to disk; pass ?regenerate=true to force refresh."""
    import json as json_mod
    import hashlib

    cfg = _require_config()
    db_path = cfg.fragments_db_path
    if not db_path.exists():
        return {"eligible": False, "reason": "没有数据"}

    store = FragmentStore(db_path)
    fragments = store.get_all()
    store.close()

    # Hash fragment contents to detect data changes
    frag_hash = hashlib.sha256(
        "".join(f"{f.source}:{f.content}" for f in fragments).encode()
    ).hexdigest()[:16]

    try:
        cache_path = cfg.percent_dir / "spectrum_cache.json"
    except TypeError:
        cache_path = None

    # Return cached result if data hasn't changed
    if not regenerate and cache_path and cache_path.exists():
        try:
            cached = json_mod.loads(cache_path.read_text(encoding="utf-8"))
            if cached.get("_hash") == frag_hash:
                cached.pop("_hash", None)
                return cached
        except (json_mod.JSONDecodeError, KeyError, TypeError):
            pass

    from percent.config import make_llm_client
    client = make_llm_client(cfg)
    prompts_dir = Path(__file__).parent / "prompts"

    card = generate_card_data(fragments, client, prompts_dir)

    result = {
        "eligible": card.spectrum.eligible,
        "reason": card.spectrum.ineligible_reason,
        "dimensions": card.spectrum.dimensions,
        "metrics": card.spectrum.metrics,
        "label": card.label,
        "description": card.description,
        "insights": card.insights,
    }

    # Persist to disk with hash
    if cache_path:
        try:
            cache_data = {**result, "_hash": frag_hash}
            cfg.percent_dir.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(
                json_mod.dumps(cache_data, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except (TypeError, OSError):
            pass

    return result


@app.get("/api/fragments/{source}")
def get_fragments_by_source(source: str) -> dict:
    """Return all fragments for a specific data source."""
    db_path = _require_config().fragments_db_path
    if not db_path.exists():
        return {"source": source, "fragments": []}
    store = FragmentStore(db_path)
    all_frags = store.get_all()
    store.close()
    filtered = [
        {
            "id": f.id,
            "category": f.category.value,
            "content": f.content,
            "confidence": f.confidence,
            "evidence": f.evidence,
            "created_at": f.created_at.isoformat() if f.created_at else "",
        }
        for f in all_frags
        if f.source == source
    ]
    # Sort by confidence descending
    filtered.sort(key=lambda x: x["confidence"], reverse=True)
    return {"source": source, "fragments": filtered}


@app.get("/api/fingerprint")
def get_fingerprint() -> dict:  # type: ignore[type-arg]
    """Return behavioral fingerprint data."""
    fp_path = _require_config().percent_dir / "fingerprint.json"
    if fp_path.exists():
        import json
        data: dict = json.loads(fp_path.read_text(encoding="utf-8"))
        return data
    return {}


@app.get("/api/big-five")
def get_big_five() -> dict:  # type: ignore[type-arg]
    """Return Big Five personality scores."""
    bf_path = _require_config().percent_dir / "big_five.json"
    if bf_path.exists():
        import json
        data: dict = json.loads(bf_path.read_text(encoding="utf-8"))
        return data
    return {}


@app.get("/api/imports")
def get_imports() -> dict:  # type: ignore[type-arg]
    """Return import history."""
    cfg = _require_config()
    manifest_path = cfg.percent_dir / "imports.json"
    if manifest_path.exists():
        import json
        data: list = json.loads(
            manifest_path.read_text(encoding="utf-8")
        )
        return {"imports": data, "total": len(data)}
    return {"imports": [], "total": 0}


@app.post("/api/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    """Send a message to the persona and get a response."""
    if _chat_engine is None:
        return ChatResponse(
            response=(
                "No personality profile loaded."
                " Run `percent import run`"
                " to build your persona first."
            )
        )
    response = _chat_engine.send(req.message)
    return ChatResponse(response=response)


@app.post("/api/chat/reset")
def reset_chat() -> dict:
    """Reset conversation history."""
    if _chat_engine is not None:
        _chat_engine.reset()
    return {"status": "ok"}


@app.get("/api/has-data")
def has_data() -> dict:
    """Check if persona data exists."""
    has_core = _config is not None and _config.core_path.exists()
    return {"has_data": has_core}


# Source name → parser class path mapping (mirrors cli.py)
_PARSER_REGISTRY = {
    "telegram": "percent.parsers.telegram.TelegramParser",
    "whatsapp": "percent.parsers.whatsapp.WhatsAppParser",
    "youtube": "percent.parsers.youtube.YouTubeParser",
    "bilibili": "percent.parsers.bilibili.BilibiliParser",
    "wechat": "percent.parsers.wechat.WeChatParser",
    "xiaohongshu": "percent.parsers.xiaohongshu.XiaohongshuParser",
}


@app.post("/api/import/upload")
async def upload_file(file: UploadFile, source: str = Form(...)) -> dict:
    """Upload a data file for import. Automatically extracts zip files."""
    import shutil
    import zipfile

    cfg = _require_config()
    raw_dir = cfg.percent_dir / "raw" / source
    raw_dir.mkdir(parents=True, exist_ok=True)
    dest = raw_dir / (file.filename or "upload")

    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)

    # Auto-extract zip files
    if dest.suffix == ".zip":
        try:
            with zipfile.ZipFile(dest, "r") as zf:
                zf.extractall(raw_dir)
            dest.unlink()  # Remove the zip after extraction
            return {
                "status": "ok",
                "path": str(raw_dir),
                "filename": file.filename,
                "extracted": True,
            }
        except zipfile.BadZipFile:
            pass  # Not a valid zip, keep as-is

    return {"status": "ok", "path": str(dest), "filename": file.filename}


class AnalyzeRequest(BaseModel):
    source: str | None = None


@app.post("/api/import/analyze")
def analyze_source(req: AnalyzeRequest | None = None) -> dict:
    """Analyze a specific source (incremental) or all sources."""
    source = req.source if req else None
    import importlib

    cfg = _require_config()
    raw_dir = cfg.percent_dir / "raw"
    if not raw_dir.exists():
        return {"status": "error", "message": "No imported files found."}

    # Handle Bilibili cookie: use API fetch instead of file parsing
    if source == "bilibili":
        cookie_path = raw_dir / "bilibili" / "bilibili_cookie.txt"
        if cookie_path.exists():
            from percent.parsers.bilibili_api import fetch_bilibili_history

            cookie = cookie_path.read_text(encoding="utf-8").strip()
            try:
                all_chunks = fetch_bilibili_history(cookie)
            except ValueError as e:
                return {"status": "error", "message": str(e)}
            if all_chunks:
                return _run_analysis(all_chunks)
            return {"status": "error", "message": "No watch history found. Check your cookie."}

    # Determine which source directories to scan
    if source and source in _PARSER_REGISTRY:
        dirs_to_scan = [raw_dir / source]
    else:
        dirs_to_scan = [d for d in raw_dir.iterdir() if d.is_dir() and d.name in _PARSER_REGISTRY]

    all_chunks = []
    for source_dir in dirs_to_scan:
        if not source_dir.exists():
            continue
        source_name = source_dir.name

        # Skip cookie text files (handled by API above)
        dotted = _PARSER_REGISTRY[source_name]
        module_path, class_name = dotted.rsplit(".", 1)
        module = importlib.import_module(module_path)
        parser = getattr(module, class_name)()

        for file_path in sorted(source_dir.rglob("*")):
            if file_path.is_file() and file_path.name.endswith("_cookie.txt"):
                continue  # Skip cookie files, they're for API fetch
            if file_path.is_file() and parser.validate(file_path):
                try:
                    chunks = parser.parse(file_path)
                    all_chunks.extend(chunks)
                except Exception:
                    pass

    if not all_chunks:
        return {"status": "error", "message": "No parseable data found in uploaded files."}

    return _run_analysis(all_chunks)


def _run_analysis(chunks: list) -> dict:
    """Run personality analysis on chunks and reinitialize chat engine."""
    cfg = _require_config()

    from percent.config import make_llm_client
    from percent.persona.engine import PersonaEngine

    client = make_llm_client(cfg)
    engine = PersonaEngine(
        client=client,
        percent_dir=cfg.percent_dir,
        prompts_dir=_PROMPTS_DIR,
        embedding_model=cfg.embedding_model,
    )

    engine.run(chunks)

    global _chat_engine
    from percent.chat.engine import ChatEngine
    _chat_engine = ChatEngine(
        percent_dir=cfg.percent_dir,
        provider=cfg.llm_provider,
        model=cfg.llm_model,
        api_key=cfg.llm_api_key,
        prompts_dir=_PROMPTS_DIR,
        embedding_model=cfg.embedding_model,
    )

    stats = engine.stats()
    return {
        "status": "ok",
        "chunks_analyzed": len(chunks),
        "total_fragments": stats.get("total", 0),
        "sources": list(stats.get("by_source", {}).keys()),
    }


@app.get("/static/{filename}")
def static_file(filename: str) -> FileResponse:
    """Serve static files."""
    path = _STATIC_DIR / filename
    if not path.exists() or not path.is_file():
        from fastapi.responses import JSONResponse
        return JSONResponse({"error": "not found"}, status_code=404)
    media_type = "application/javascript" if filename.endswith(".js") else None
    return FileResponse(path, media_type=media_type)


@app.get("/")
def index() -> FileResponse:
    """Serve the main UI."""
    return FileResponse(_STATIC_DIR / "index.html")


def start_server(port: int = 18900) -> None:
    """Start the uvicorn server."""
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")
