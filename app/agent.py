import json
import os
import threading

from langchain_core.runnables import RunnableConfig
from langchain_ollama import ChatOllama
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import START, StateGraph
from langgraph.types import Command, interrupt  # noqa: F401

from app.state import MATRIX_TEMPLATES, ResearchState
from app.tools import search_arxiv, search_scholar

# ---------------------------------------------------------------------------
# Matrix streaming registry  (session_id → (asyncio.Queue, event_loop))
# ---------------------------------------------------------------------------
_matrix_streams: dict = {}
_stream_lock = threading.Lock()


def _reg_stream(tid: str, q, loop) -> None:
    with _stream_lock:
        _matrix_streams[tid] = (q, loop)


def _unreg_stream(tid: str) -> None:
    with _stream_lock:
        _matrix_streams.pop(tid, None)

MODEL = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
OLLAMA_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")


def get_llm(temperature: float = 0.3):
    return ChatOllama(
        model=MODEL,
        temperature=temperature,
        num_predict=4096,
        base_url=OLLAMA_URL,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_equation_response(content: str) -> tuple[str, str]:
    """Extract equation and explanation from structured LLM output."""
    equation = ""
    explanation = ""
    lines = content.split("\n")
    section = None

    for line in lines:
        upper = line.upper().strip()
        if "ECUACIÓN:" in upper or "EQUATION:" in upper or "BOOLEAN:" in upper:
            section = "eq"
            continue
        if "EXPLICACIÓN:" in upper or "EXPLICACION:" in upper or "JUSTIFICACIÓN:" in upper or "EXPLANATION:" in upper:
            section = "exp"
            continue
        if "ARXIV:" in upper:
            section = "arxiv"
            continue

        if section == "eq" and line.strip() and not equation:
            equation = line.strip()
        elif section == "exp" and line.strip():
            explanation += line.strip() + " "

    # Fallback: first line containing boolean operators
    if not equation:
        for line in lines:
            if any(op in line for op in [" AND ", " OR ", " NOT "]):
                equation = line.strip()
                break
    # Last fallback
    if not equation:
        equation = content.strip().split("\n")[0]

    return equation.strip('"').strip("'"), explanation.strip()


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------

def node_ask_needs(state: ResearchState):
    user_input = interrupt({
        "type": "question",
        "stage": "ask_needs",
        "content": (
            "¡Hola! Soy tu **asistente de investigación académica**.\n\n"
            "Te ayudaré a:\n"
            "1. Construir una **ecuación de búsqueda booleana** elaborada\n"
            "2. Capturar artículos de **ArXiv** y **Google Scholar**\n"
            "3. Generar una **matriz bibliográfica** con datos bibliométricos\n"
            "4. Responder **preguntas** sobre la literatura encontrada\n\n"
            "**¿Sobre qué tema necesitas investigar?** Cuéntame tu tema, pregunta "
            "de investigación o área de interés. Cuanto más detallado, mejor."
        ),
    })
    return {"research_needs": user_input, "stage": "generate_equation"}


def node_generate_equation(state: ResearchState):
    llm = get_llm()
    prompt = (
        "Eres un experto en búsqueda bibliográfica científica. "
        "Construye una ecuación de búsqueda booleana ELABORADA y PRECISA.\n\n"
        f"TEMA: \"{state['research_needs']}\"\n\n"
        "PROCESO:\n"
        "1. Identifica 2-4 conceptos centrales\n"
        "2. Para cada concepto, lista 3-5 sinónimos o variantes en inglés\n"
        "3. Agrupa sinónimos con OR, une conceptos con AND\n"
        "4. Añade NOT para excluir ruido (surveys, tutorials si no son relevantes)\n"
        "5. Usa comillas para frases exactas, asterisco (*) para variantes morfológicas\n\n"
        "FORMATO DE RESPUESTA (exactamente así):\n"
        "ECUACIÓN:\n"
        "(concepto1 OR \"frase exacta\" OR variant*) AND (concepto2 OR sinonimo) AND NOT (excluir)\n\n"
        "EXPLICACIÓN:\n"
        "Breve descripción de los conceptos identificados y la lógica de la ecuación.\n"
    )
    response = llm.invoke(prompt)
    equation, explanation = _parse_equation_response(response.content)
    return {
        "search_equation": equation,
        "equation_explanation": explanation,
        "stage": "adjust_equation",
    }


def node_adjust_equation(state: ResearchState):
    user_response = interrupt({
        "type": "equation",
        "stage": "adjust_equation",
        "content": "Revisa la ecuación de búsqueda generada. Puedes editarla o confirmarla:",
        "equation": state["search_equation"],
        "explanation": state.get("equation_explanation", ""),
    })

    # UI sends {"equation": "...", "count": 10}  or a plain string
    if isinstance(user_response, dict):
        eq_text = user_response.get("equation", "confirmar")
        paper_count = max(1, min(25, int(user_response.get("count", 10))))
    else:
        eq_text = str(user_response)
        paper_count = 10

    confirm_words = {
        "confirmar", "confirm", "ok", "sí", "si", "yes",
        "listo", "usar", "continuar", "aceptar", "",
    }
    final_equation = (
        state["search_equation"] if eq_text.lower().strip() in confirm_words
        else eq_text.strip()
    )

    return {
        "search_equation": final_equation,
        "paper_count": paper_count,
        "stage": "fetch_papers",
    }


def node_fetch_papers(state: ResearchState):
    count = state.get("paper_count") or 5
    equation = state["search_equation"]
    arxiv_papers = search_arxiv(equation, max_results=count)
    scholar_papers = search_scholar(equation, max_results=count)
    all_papers = arxiv_papers + scholar_papers
    valid = [
        p for p in all_papers
        if p.get("title") and len(p["title"]) > 5 and p.get("abstract", "")
    ]
    return {"papers": valid if valid else all_papers, "stage": "ask_matrix"}


def node_ask_matrix(state: ResearchState):
    user_response = interrupt({
        "type": "papers",
        "stage": "ask_matrix",
        "content": "¿Cómo quieres la **matriz bibliográfica**? Elige una plantilla o describe tu formato:",
        "papers": state["papers"],
        "templates": MATRIX_TEMPLATES,
    })

    # UI sends {"template_id": "...", "custom": "..."} or plain string
    if isinstance(user_response, dict):
        template_id = user_response.get("template_id", "")
        custom = user_response.get("custom", "").strip()
        base_format = ""
        for t in MATRIX_TEMPLATES:
            if t["id"] == template_id:
                base_format = t["format"]
                break
        if base_format and custom:
            final_format = f"{base_format}. Además: {custom}"
        elif base_format:
            final_format = base_format
        else:
            final_format = custom or "tabla comparativa estándar con datos bibliométricos"
    else:
        template_id = ""
        final_format = str(user_response)

    return {
        "matrix_format": final_format,
        "matrix_template": template_id,
        "stage": "generate_matrix",
    }


def node_generate_matrix(state: ResearchState, config: RunnableConfig = None):
    llm = get_llm()
    papers_json = json.dumps(state["papers"], ensure_ascii=False, indent=2)
    prompt = (
        "Eres un experto en gestión y análisis bibliográfico.\n\n"
        f"ARTÍCULOS ACADÉMICOS:\n{papers_json}\n\n"
        f"FORMATO SOLICITADO:\n{state['matrix_format']}\n\n"
        "INSTRUCCIONES:\n"
        "1. Genera la matriz como tabla Markdown completa y bien estructurada\n"
        "2. Incluye TODOS los artículos sin excepción\n"
        "3. Si falta información deja la celda vacía, no escribas N/D\n"
        "4. Escribe celdas DETALLADAS: 3-5 frases por celda descriptiva; sé específico y técnico\n"
        "5. En celdas de metodología: describe el enfoque, arquitectura o técnica en detalle\n"
        "6. En celdas de resultados: incluye métricas numéricas exactas cuando existan\n"
        "7. En celdas de limitaciones: identifica al menos 2-3 limitaciones concretas del trabajo\n"
        "8. Incluye siempre DOI y Citas cuando estén disponibles\n"
        "9. Al final añade ## Análisis General con las siguientes secciones:\n"
        "   - **Tendencias dominantes**: al menos 5 observaciones sobre patrones y enfoques emergentes\n"
        "   - **Brechas identificadas**: gaps de investigación no cubiertos por la literatura actual\n"
        "   - **Convergencias metodológicas**: técnicas o frameworks compartidos entre estudios\n"
        "   - **Evolución temporal**: cómo ha evolucionado el campo entre los años de los artículos\n"
        "   - **Recomendaciones de lectura**: prioridad de lectura justificada con criterios bibliométricos\n\n"
        "Genera la matriz completa y detallada:"
    )

    tid = (config or {}).get("configurable", {}).get("thread_id", "") if config else ""
    with _stream_lock:
        stream_info = _matrix_streams.get(tid)

    full_content = ""
    if stream_info:
        q, loop = stream_info
        try:
            for chunk in llm.stream(prompt):
                full_content += chunk.content
                loop.call_soon_threadsafe(q.put_nowait, chunk.content)
        finally:
            loop.call_soon_threadsafe(q.put_nowait, None)
    else:
        try:
            full_content = llm.invoke(prompt).content
        except Exception:
            full_content = ""

    return {"matrix": full_content, "stage": "generate_hypotheses"}


def node_generate_hypotheses(state: ResearchState):
    try:
        llm = ChatOllama(
            model=MODEL,
            temperature=0.5,
            num_predict=1024,
            base_url=OLLAMA_URL,
        )
        papers_json = json.dumps([{
            "title": p.get("title", ""),
            "abstract": p.get("abstract", "")[:300],
            "year": p.get("year", ""),
            "keywords": p.get("keywords", ""),
        } for p in state["papers"]], ensure_ascii=False, indent=2)

        prompt = (
            "Eres un experto en metodología de investigación científica. "
            "Analiza los artículos y propón hipótesis originales que llenen brechas reales.\n\n"
            f"TEMA: {state['research_needs']}\n\n"
            f"ARTÍCULOS:\n{papers_json}\n\n"
            "Genera exactamente 4 hipótesis de investigación originales y testeables. "
            "Responde ÚNICAMENTE con un JSON array válido, sin texto adicional:\n"
            "[\n"
            "  {\n"
            '    "hypothesis": "H1: Enunciado claro y testeable",\n'
            '    "gap": "Brecha que aborda: qué no ha sido estudiado aún",\n'
            '    "methodology": "Enfoque metodológico sugerido para validarla",\n'
            '    "novelty": 8\n'
            "  }\n"
            "]\n"
            "novelty: 1 (incremental) a 10 (disruptivo). Solo el JSON array."
        )
        response = llm.invoke(prompt)
        raw = response.content.strip()
        hypotheses = []
        try:
            start = raw.find("[")
            end = raw.rfind("]") + 1
            if start >= 0 and end > start:
                hypotheses = json.loads(raw[start:end])
        except Exception:
            pass
        return {"hypotheses": hypotheses, "stage": "qa"}
    except Exception:
        return {"hypotheses": [], "stage": "qa"}


def node_qa(state: ResearchState):
    first_call = len(state.get("chat_history", [])) == 0

    user_input = interrupt({
        "type": "qa",
        "stage": "qa",
        "show_matrix": first_call,
        "matrix": state.get("matrix") if first_call else None,
        "hypotheses": state.get("hypotheses", []) if first_call else None,
        "last_answer": state.get("last_answer") or None,
    })

    llm = get_llm(temperature=0.2)
    papers_brief = json.dumps(
        [
            {
                "title": p["title"],
                "authors": p["authors"],
                "year": p["year"],
                "abstract": p["abstract"][:300],
                "source": p["source"],
                "journal": p.get("journal", ""),
                "citations": p.get("citations", ""),
                "doi": p.get("doi", ""),
                "url": p["url"],
            }
            for p in state["papers"]
        ],
        ensure_ascii=False,
        indent=2,
    )

    history_text = "".join(
        f"{'Usuario' if m['role'] == 'user' else 'Asistente'}: {m['content'][:400]}\n\n"
        for m in state.get("chat_history", [])[-6:]
    )

    prompt = (
        "Eres un asistente de investigación académica experto.\n\n"
        f"ARTÍCULOS DISPONIBLES:\n{papers_brief}\n\n"
        f"ECUACIÓN DE BÚSQUEDA: {state['search_equation']}\n\n"
        f"HISTORIAL:\n{history_text}\n"
        f"PREGUNTA: {user_input}\n\n"
        "Responde de forma informada. Cita artículos específicos (autor, año) cuando sea relevante. "
        "Usa Markdown. Si la pregunta está fuera del alcance, responde con tu conocimiento general."
    )
    answer = llm.invoke(prompt)

    new_history = list(state.get("chat_history", [])) + [
        {"role": "user", "content": user_input},
        {"role": "assistant", "content": answer.content},
    ]
    return {"chat_history": new_history, "last_answer": answer.content, "stage": "qa"}


# ---------------------------------------------------------------------------
# Graph
# ---------------------------------------------------------------------------

def _build_graph():
    builder = StateGraph(ResearchState)

    for name, fn in [
        ("ask_needs", node_ask_needs),
        ("generate_equation", node_generate_equation),
        ("adjust_equation", node_adjust_equation),
        ("fetch_papers", node_fetch_papers),
        ("ask_matrix", node_ask_matrix),
        ("generate_matrix", node_generate_matrix),
        ("generate_hypotheses", node_generate_hypotheses),
        ("qa", node_qa),
    ]:
        builder.add_node(name, fn)

    builder.add_edge(START, "ask_needs")
    builder.add_edge("ask_needs", "generate_equation")
    builder.add_edge("generate_equation", "adjust_equation")
    builder.add_edge("adjust_equation", "fetch_papers")
    builder.add_edge("fetch_papers", "ask_matrix")
    builder.add_edge("ask_matrix", "generate_matrix")
    builder.add_edge("generate_matrix", "generate_hypotheses")
    builder.add_edge("generate_hypotheses", "qa")
    builder.add_conditional_edges("qa", lambda _: "qa", {"qa": "qa"})

    return builder.compile(checkpointer=MemorySaver())


graph = _build_graph()

INITIAL_STATE: ResearchState = {
    "stage": "ask_needs",
    "research_needs": "",
    "search_equation": "",
    "equation_explanation": "",
    "paper_count": 5,
    "papers": [],
    "matrix_template": "",
    "matrix_format": "",
    "matrix": "",
    "hypotheses": [],
    "chat_history": [],
    "last_answer": "",
}
