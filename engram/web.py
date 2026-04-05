"""Engram Web UI — FastAPI server with chat interface and persona viewer."""

from __future__ import annotations

from pathlib import Path

import uvicorn
from fastapi import FastAPI, Form, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from engram.config import load_config
from engram.persona.fragments import FragmentStore

app = FastAPI(title="Engram", description="Open-source personality modeling engine")

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
        from engram.chat.engine import ChatEngine

        _chat_engine = ChatEngine(
            engram_dir=_config.engram_dir,
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
    return {"content": "No personality profile yet. Run `engram import run` first."}


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
    fp_path = _config.engram_dir / "fingerprint.json"
    if fp_path.exists():
        import json
        return json.loads(fp_path.read_text(encoding="utf-8"))
    return {}


@app.post("/api/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    """Send a message to the persona and get a response."""
    if _chat_engine is None:
        return ChatResponse(
            response="No personality profile loaded. Run `engram import run` to build your persona first."
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
    "telegram": "engram.parsers.telegram.TelegramParser",
    "whatsapp": "engram.parsers.whatsapp.WhatsAppParser",
    "youtube": "engram.parsers.youtube.YouTubeParser",
    "bilibili": "engram.parsers.bilibili.BilibiliParser",
    "wechat": "engram.parsers.wechat.WeChatParser",
}


@app.post("/api/import/upload")
async def upload_file(file: UploadFile, source: str = Form(...)) -> dict:
    """Upload a data file for import. Automatically extracts zip files."""
    import shutil
    import zipfile

    raw_dir = _config.engram_dir / "raw" / source
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


@app.post("/api/import/analyze")
def analyze_imported() -> dict:
    """Run personality analysis on all imported files under ~/.engram/raw/."""
    import importlib

    raw_dir = _config.engram_dir / "raw"
    if not raw_dir.exists():
        return {"status": "error", "message": "No imported files found."}

    all_chunks = []

    for source_dir in raw_dir.iterdir():
        if not source_dir.is_dir():
            continue
        source_name = source_dir.name
        if source_name not in _PARSER_REGISTRY:
            continue

        dotted = _PARSER_REGISTRY[source_name]
        module_path, class_name = dotted.rsplit(".", 1)
        module = importlib.import_module(module_path)
        parser = getattr(module, class_name)()

        # Scan all files recursively (handles extracted zip subdirectories)
        for file_path in sorted(source_dir.rglob("*")):
            if file_path.is_file() and parser.validate(file_path):
                try:
                    chunks = parser.parse(file_path)
                    all_chunks.extend(chunks)
                except Exception:
                    pass  # Skip unparseable files

    if not all_chunks:
        return {"status": "error", "message": "No parseable data found in uploaded files."}

    from engram.llm.client import LLMClient
    from engram.persona.engine import PersonaEngine

    client = LLMClient(
        provider=_config.llm_provider,
        model=_config.llm_model,
        api_key=_config.llm_api_key,
    )
    engine = PersonaEngine(
        client=client,
        engram_dir=_config.engram_dir,
        prompts_dir=_PROMPTS_DIR,
        embedding_model=_config.embedding_model,
    )
    engine.run(all_chunks)

    # Reinitialize chat engine now that core.md exists
    global _chat_engine
    if _chat_engine is None and _config.core_path.exists():
        from engram.chat.engine import ChatEngine

        _chat_engine = ChatEngine(
            engram_dir=_config.engram_dir,
            provider=_config.llm_provider,
            model=_config.llm_model,
            api_key=_config.llm_api_key,
            prompts_dir=_PROMPTS_DIR,
            embedding_model=_config.embedding_model,
        )

    core_content = _config.core_path.read_text(encoding="utf-8") if _config.core_path.exists() else ""
    return {"status": "ok", "chunks_analyzed": len(all_chunks), "core_md": core_content}


@app.get("/")
def index() -> FileResponse:
    """Serve the main UI."""
    return FileResponse(_STATIC_DIR / "index.html")


def start_server(port: int = 18900) -> None:
    """Start the uvicorn server."""
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")
