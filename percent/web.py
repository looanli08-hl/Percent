"""Percent Web UI — FastAPI server with chat interface and persona viewer."""

from __future__ import annotations

from pathlib import Path

import uvicorn
from fastapi import FastAPI, Form, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from percent.config import load_config
from percent.persona.fragments import FragmentStore

app = FastAPI(title="Percent", description="Open-source personality modeling engine")

# Global state (initialized on startup)
_chat_engine = None
_config = None

_PROMPTS_DIR = Path(__file__).parent.parent / "prompts"
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
    core_path = _config.core_path
    if core_path.exists():
        return {"content": core_path.read_text(encoding="utf-8")}
    return {"content": "No personality profile yet. Run `percent import run` first."}


@app.get("/api/stats")
def get_stats() -> dict:
    """Return fragment statistics."""
    db_path = _config.fragments_db_path
    if not db_path.exists():
        return {"total": 0, "by_source": {}, "by_category": {}}
    store = FragmentStore(db_path)
    stats = store.stats()
    store.close()
    return stats


@app.get("/api/fingerprint")
def get_fingerprint() -> dict:
    """Return behavioral fingerprint data."""
    fp_path = _config.percent_dir / "fingerprint.json"
    if fp_path.exists():
        import json
        return json.loads(fp_path.read_text(encoding="utf-8"))
    return {}


@app.get("/api/big-five")
def get_big_five() -> dict:
    """Return Big Five personality scores."""
    bf_path = _config.percent_dir / "big_five.json"
    if bf_path.exists():
        import json
        return json.loads(bf_path.read_text(encoding="utf-8"))
    return {}


@app.post("/api/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    """Send a message to the persona and get a response."""
    if _chat_engine is None:
        return ChatResponse(
            response="No personality profile loaded. Run `percent import run` to build your persona first."
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
    has_core = _config.core_path.exists() if _config else False
    return {"has_data": has_core}


# Source name → parser class path mapping (mirrors cli.py)
_PARSER_REGISTRY = {
    "telegram": "percent.parsers.telegram.TelegramParser",
    "whatsapp": "percent.parsers.whatsapp.WhatsAppParser",
    "youtube": "percent.parsers.youtube.YouTubeParser",
    "bilibili": "percent.parsers.bilibili.BilibiliParser",
    "wechat": "percent.parsers.wechat.WeChatParser",
}


@app.post("/api/import/upload")
async def upload_file(file: UploadFile, source: str = Form(...)) -> dict:
    """Upload a data file for import. Automatically extracts zip files."""
    import shutil
    import zipfile

    raw_dir = _config.percent_dir / "raw" / source
    raw_dir.mkdir(parents=True, exist_ok=True)
    dest = raw_dir / file.filename

    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)

    # Auto-extract zip files
    if dest.suffix == ".zip":
        try:
            with zipfile.ZipFile(dest, "r") as zf:
                zf.extractall(raw_dir)
            dest.unlink()  # Remove the zip after extraction
            return {"status": "ok", "path": str(raw_dir), "filename": file.filename, "extracted": True}
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

    raw_dir = _config.percent_dir / "raw"
    if not raw_dir.exists():
        return {"status": "error", "message": "No imported files found."}

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

        dotted = _PARSER_REGISTRY[source_name]
        module_path, class_name = dotted.rsplit(".", 1)
        module = importlib.import_module(module_path)
        parser = getattr(module, class_name)()

        for file_path in sorted(source_dir.rglob("*")):
            if file_path.is_file() and parser.validate(file_path):
                try:
                    chunks = parser.parse(file_path)
                    all_chunks.extend(chunks)
                except Exception:
                    pass

    if not all_chunks:
        return {"status": "error", "message": "No parseable data found in uploaded files."}

    from percent.llm.client import LLMClient
    from percent.persona.engine import PersonaEngine

    client = LLMClient(
        provider=_config.llm_provider,
        model=_config.llm_model,
        api_key=_config.llm_api_key,
    )
    engine = PersonaEngine(
        client=client,
        percent_dir=_config.percent_dir,
        prompts_dir=_PROMPTS_DIR,
        embedding_model=_config.embedding_model,
    )

    # run() is already incremental:
    # - extracts new findings → appends to fragments.db
    # - re-synthesizes core.md from ALL fragments (old + new)
    engine.run(all_chunks)

    # Initialize or reinitialize chat engine with updated persona
    global _chat_engine
    from percent.chat.engine import ChatEngine
    _chat_engine = ChatEngine(
        percent_dir=_config.percent_dir,
        provider=_config.llm_provider,
        model=_config.llm_model,
        api_key=_config.llm_api_key,
        prompts_dir=_PROMPTS_DIR,
        embedding_model=_config.embedding_model,
    )

    stats = engine.stats()
    return {
        "status": "ok",
        "chunks_analyzed": len(all_chunks),
        "total_fragments": stats.get("total", 0),
        "sources": list(stats.get("by_source", {}).keys()),
    }


@app.get("/")
def index() -> FileResponse:
    """Serve the main UI."""
    return FileResponse(_STATIC_DIR / "index.html")


def start_server(port: int = 18900) -> None:
    """Start the uvicorn server."""
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")
