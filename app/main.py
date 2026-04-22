import asyncio
import uuid
from datetime import datetime
from io import BytesIO
from pathlib import Path

import openpyxl
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from langgraph.types import Command

from app.agent import INITIAL_STATE, graph

STATIC_DIR = Path(__file__).parent.parent / "static"

app = FastAPI(title="ResearchAgent")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
async def root():
    return FileResponse(str(STATIC_DIR / "index.html"))


@app.get("/api/session")
async def create_session():
    return {"session_id": str(uuid.uuid4())}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_config(session_id: str) -> dict:
    return {"configurable": {"thread_id": session_id}}


def _get_interrupt_value(session_id: str) -> dict | None:
    state = graph.get_state(_get_config(session_id))
    if state.next:
        for task in state.tasks:
            for interrupt_obj in task.interrupts:
                return interrupt_obj.value
    return None


def _parse_markdown_table(markdown: str) -> list[list[str]]:
    rows = []
    for line in markdown.split("\n"):
        line = line.strip()
        if line.startswith("|") and line.endswith("|") and "---" not in line:
            cells = [c.strip() for c in line[1:-1].split("|")]
            rows.append(cells)
    return rows


STATUS_BY_TYPE = {
    "question": "🧠 Generando ecuación de búsqueda elaborada...",
    "equation": "🔍 Buscando artículos en ArXiv y Google Scholar...",
    "papers": "📊 Generando matriz bibliográfica...",
    "qa": "💭 Analizando tu pregunta...",
}


# ---------------------------------------------------------------------------
# XLSX download
# ---------------------------------------------------------------------------

HDR_FILL = PatternFill(start_color="1e3a5f", end_color="1e3a5f", fill_type="solid")
HDR_FONT = Font(color="93c5fd", bold=True)
ALT_FILL = PatternFill(start_color="0f2137", end_color="0f2137", fill_type="solid")
WRAP = Alignment(wrap_text=True, vertical="top")


def _set_header(ws, col: int, row: int, value: str):
    c = ws.cell(row=row, column=col, value=value)
    c.fill = HDR_FILL
    c.font = HDR_FONT
    c.alignment = WRAP


@app.get("/api/download/xlsx/{session_id}")
async def download_xlsx(session_id: str):
    config = _get_config(session_id)
    snap = graph.get_state(config)
    if not snap.values:
        return {"error": "Sesión no encontrada"}

    vals = snap.values
    papers = vals.get("papers", [])
    matrix_md = vals.get("matrix", "")
    equation = vals.get("search_equation", "")
    needs = vals.get("research_needs", "")
    paper_count = vals.get("paper_count", 5)

    wb = openpyxl.Workbook()

    # ── Sheet 1: Artículos ──────────────────────────────────────────────────
    ws1 = wb.active
    ws1.title = "Artículos"

    cols1 = [
        ("#", 4), ("Título", 48), ("Autores", 28), ("Año", 6),
        ("Fuente", 14), ("Revista / Conferencia", 30), ("DOI", 24),
        ("Citas", 8), ("Open Access", 12), ("Palabras Clave", 28),
        ("Volumen", 8), ("Número", 8), ("Páginas", 10), ("URL", 50),
    ]
    for i, (header, width) in enumerate(cols1, 1):
        _set_header(ws1, i, 1, header)
        ws1.column_dimensions[get_column_letter(i)].width = width

    for i, p in enumerate(papers, 1):
        row = i + 1
        values = [
            i, p.get("title", ""), p.get("authors", ""), p.get("year", ""),
            p.get("source", ""), p.get("journal", ""), p.get("doi", ""),
            p.get("citations", ""), p.get("open_access", ""), p.get("keywords", ""),
            p.get("volume", ""), p.get("issue", ""), p.get("pages", ""), p.get("url", ""),
        ]
        for col, val in enumerate(values, 1):
            cell = ws1.cell(row=row, column=col, value=val)
            cell.alignment = WRAP
            if i % 2 == 0:
                cell.fill = ALT_FILL

    # ── Sheet 2: Matriz ─────────────────────────────────────────────────────
    ws2 = wb.create_sheet("Matriz Bibliográfica")
    if matrix_md:
        rows = _parse_markdown_table(matrix_md)
        for r, row_data in enumerate(rows, 1):
            for c, val in enumerate(row_data, 1):
                cell = ws2.cell(row=r, column=c, value=val)
                cell.alignment = WRAP
                if r == 1:
                    cell.fill = HDR_FILL
                    cell.font = HDR_FONT
                elif r % 2 == 0:
                    cell.fill = ALT_FILL
        max_col = max((len(r) for r in rows), default=1)
        for c in range(1, max_col + 1):
            ws2.column_dimensions[get_column_letter(c)].width = 28

    # ── Sheet 3: Búsqueda ───────────────────────────────────────────────────
    ws3 = wb.create_sheet("Búsqueda")
    meta = [
        ("Tema de investigación", needs),
        ("Ecuación de búsqueda", equation),
        ("Papers por fuente", paper_count),
        ("Total artículos", len(papers)),
        ("ArXiv", sum(1 for p in papers if p.get("source") == "ArXiv")),
        ("Google Scholar", sum(1 for p in papers if p.get("source") == "Google Scholar")),
        ("Fecha de búsqueda", datetime.now().strftime("%Y-%m-%d %H:%M")),
        ("Modelo LLM", "llama3.1:8b (Ollama)"),
    ]
    for r, (k, v) in enumerate(meta, 1):
        ws3.cell(row=r, column=1, value=k).font = Font(bold=True)
        ws3.cell(row=r, column=2, value=str(v)).alignment = WRAP
    ws3.column_dimensions["A"].width = 28
    ws3.column_dimensions["B"].width = 65

    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)

    filename = f"matriz_bibliografica_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


# ---------------------------------------------------------------------------
# WebSocket
# ---------------------------------------------------------------------------

@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await websocket.accept()
    config = _get_config(session_id)

    try:
        existing = graph.get_state(config)
        if existing.values:
            iv = _get_interrupt_value(session_id)
            if iv:
                await websocket.send_json(iv)
        else:
            await asyncio.to_thread(graph.invoke, dict(INITIAL_STATE), config)
            iv = _get_interrupt_value(session_id)
            if iv:
                await websocket.send_json(iv)

        while True:
            data = await websocket.receive_json()

            current_iv = _get_interrupt_value(session_id)
            current_type = (current_iv or {}).get("type", "")

            status_msg = STATUS_BY_TYPE.get(current_type)
            if status_msg:
                await websocket.send_json({"type": "status", "content": status_msg})

            # Build resume value: pass structured dicts for equation / papers stages
            if current_type == "equation":
                resume_value = {
                    "equation": data.get("content", "confirmar"),
                    "count": data.get("count", 5),
                }
            elif current_type == "papers":
                resume_value = {
                    "template_id": data.get("template_id", ""),
                    "custom": data.get("content", ""),
                }
            else:
                resume_value = data.get("content", "").strip()
                if not resume_value:
                    continue

            await asyncio.to_thread(graph.invoke, Command(resume=resume_value), config)

            new_iv = _get_interrupt_value(session_id)
            if new_iv:
                await websocket.send_json(new_iv)
            else:
                await websocket.send_json({"type": "complete", "content": "Sesión completada."})

    except WebSocketDisconnect:
        pass
    except Exception as exc:
        try:
            await websocket.send_json({"type": "error", "content": str(exc)})
        except Exception:
            pass
