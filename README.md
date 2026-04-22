# ResearchAgent — DataHack 2026

> Asistente multiagente para descubrir, analizar y comparar literatura científica de ArXiv y Google Scholar — con ecuaciones de búsqueda booleanas elaboradas, matrices bibliográficas exportables y Q&A conversacional, todo corriendo localmente con un LLM de ~7 GB.

---

## Tabla de contenido

1. [¿Qué hace?](#qué-hace)
2. [Demo del flujo](#demo-del-flujo)
3. [Requisitos previos](#requisitos-previos)
4. [Instalación](#instalación)
5. [Ejecución](#ejecución)
6. [Modelos disponibles](#modelos-disponibles)
7. [Plantillas de matrices](#plantillas-de-matrices)
8. [Arquitectura](#arquitectura)
9. [Estructura del proyecto](#estructura-del-proyecto)
10. [Variables de entorno](#variables-de-entorno)
11. [Fuentes de datos](#fuentes-de-datos)
12. [Stack tecnológico](#stack-tecnológico)
13. [Solución de problemas](#solución-de-problemas)

---

## ¿Qué hace?

ResearchAgent es un asistente conversacional que guía al investigador por un flujo estructurado de 7 etapas:

| # | Etapa | Descripción |
|---|---|---|
| 1 | **Necesidades** | El agente pregunta sobre el tema de investigación |
| 2 | **Ecuación** | Genera una ecuación booleana elaborada (sinónimos, operadores de campo, wildcards) |
| 3 | **Ajuste** | El usuario edita o confirma la ecuación y elige cuántos papers capturar (1–20 por fuente) |
| 4 | **Búsqueda** | Captura papers de ArXiv y Google Scholar con datos bibliométricos completos |
| 5 | **Formato** | El usuario elige entre 6 plantillas de matriz bibliográfica o define su propio formato |
| 6 | **Matriz** | Genera tabla Markdown con análisis de tendencias + exportación a Excel (.xlsx) |
| 7 | **Q&A** | Responde preguntas sobre los artículos: comparaciones, brechas, recomendaciones |

### Características principales

- **Clippy** — mascota paperclip animada (SVG) con tips contextuales por etapa
- **Ecuaciones elaboradas** — AND / OR / NOT, frases exactas, wildcards (`classif*`), operadores de campo ArXiv (`ti:`, `abs:`)
- **Datos bibliométricos** — DOI, citas, revista/conferencia, Open Access, volumen, número, páginas, URL al PDF
- **6 plantillas de matriz** — Estado del Arte, Revisión Sistemática, Benchmarking, Marco Teórico, Tendencias, Meta-análisis
- **Descarga XLSX** — 3 hojas: Artículos, Matriz Bibliográfica, Metadatos de búsqueda
- **100 % local** — no requiere API keys, el LLM corre en tu máquina con Ollama
- **Sesiones persistentes** — reconectar al mismo `session_id` retoma donde lo dejaste

---

## Demo del flujo

```
Usuario:  "quiero investigar transformers para diagnóstico de enfermedades raras"

Agente:   ECUACIÓN:
          ("transformer" OR "BERT" OR "vision transformer" OR "ViT") AND
          ("rare disease" OR "orphan disease" OR "rare disorder") AND
          ("diagnosis" OR "classification" OR "detection") AND NOT ("survey" OR "review")

          EXPLICACIÓN:
          Se identificaron 3 conceptos centrales: arquitectura transformer,
          enfermedades raras y tarea de diagnóstico. Se excluyeron surveys
          para priorizar trabajos experimentales.

          [slider] Papers por fuente: 8

Usuario:  ✅ Confirmar ecuación · 8 papers por fuente

Agente:   [16 paper cards con DOI, citas, PDF link…]
          ¿Cómo quieres la matriz bibliográfica?

Usuario:  [selecciona plantilla "Benchmarking Técnico"]

Agente:   | Autores | Año | Modelo | Dataset | Accuracy | F1 | DOI |
          |---------|-----|--------|---------|----------|----|-----|
          | …       | …   | …      | …       | …        | …  | …   |
          [📊 Descargar XLSX]

Usuario:  "¿Cuál de estos artículos tiene el mejor F1 y usa datos públicos?"
Agente:   Basándome en los artículos encontrados, Chen et al. (2023)…
```

---

## Requisitos previos

| Herramienta | Versión mínima | Instalación |
|---|---|---|
| [uv](https://docs.astral.sh/uv/) | cualquiera | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| [Ollama](https://ollama.com) | 0.3+ | [ollama.com/download](https://ollama.com/download) |
| Python | 3.10+ | incluido con uv |

---

## Instalación

```bash
# 1. Clona el repositorio
git clone <url-del-repo>
cd ResearchAgent-DataHack2026

# 2. Crea el entorno virtual e instala dependencias
uv venv
uv pip install -r requirements.txt

# 3. Descarga el modelo de lenguaje
ollama pull llama3.1:8b          # recomendado — 4.7 GB, excelente balance
```

---

## Ejecución

```bash
# Terminal 1 — servidor Ollama (si no está ya corriendo como servicio)
ollama serve

# Terminal 2 — aplicación web
uv run uvicorn app.main:app --reload
```

Abre **http://localhost:8000** en tu navegador.

---

## Modelos disponibles

Cualquier modelo en Ollama funciona. Estos son los más recomendados:

| Modelo | Tamaño | Comando | Notas |
|---|---|---|---|
| `llama3.1:8b` | 4.7 GB | `ollama pull llama3.1:8b` | **Recomendado** — rápido y preciso |
| `qwen2.5:7b-instruct-q8_0` | 7.6 GB | `ollama pull qwen2.5:7b-instruct-q8_0` | ~7 GB exactos, muy bueno en español |
| `mistral:7b-instruct-v0.3-q8_0` | 7.7 GB | `ollama pull mistral:7b-instruct-v0.3-q8_0` | ~7 GB, sólido para textos técnicos |
| `llama3.1:8b-instruct-q6_K` | 6.6 GB | `ollama pull llama3.1:8b-instruct-q6_K` | buen balance calidad/tamaño |

Para usar un modelo diferente al por defecto:

```bash
OLLAMA_MODEL=qwen2.5:7b-instruct-q8_0 uv run uvicorn app.main:app --reload
```

---

## Plantillas de matrices

El agente incluye 6 plantillas diseñadas para distintos propósitos de investigación. Todas incluyen datos bibliométricos clave (DOI, citas, revista).

| Plantilla | Icono | Columnas principales |
|---|---|---|
| **Estado del Arte** | 🗺️ | Técnica, Dataset, Métricas, Aportes, Limitaciones |
| **Revisión Sistemática** | 🔬 | Tipo de estudio, Nivel de evidencia, Riesgo de sesgo |
| **Benchmarking Técnico** | 📊 | Accuracy, Precision, Recall, F1, AUC, Hardware |
| **Marco Teórico** | 📚 | Concepto, Definición, Dimensiones, Contexto |
| **Tendencias e Innovación** | 📈 | TRL, Impacto, Barreras, Oportunidades |
| **Meta-análisis** | 🧮 | N estudios, Efecto promedio, IC 95%, I² |

Adicionalmente se puede combinar cualquier plantilla con columnas personalizadas desde la interfaz.

---

## Arquitectura

### Grafo LangGraph

```
START
  │
  ▼
ask_needs ──[interrupt: espera tema]──► generate_equation
                                              │
                                              ▼
                                       adjust_equation ──[interrupt: muestra ecuación]
                                              │
                                        (dict: {equation, count})
                                              │
                                              ▼
                                        fetch_papers ──► ArXiv API + scholarly
                                              │
                                              ▼
                                        ask_matrix ──[interrupt: muestra papers + plantillas]
                                              │
                                        (dict: {template_id, custom})
                                              │
                                              ▼
                                       generate_matrix ──► LLM genera tabla MD
                                              │
                                              ▼
                                           qa ◄─────────────────────────────┐
                                             │                               │
                                             └──[interrupt: muestra respuesta]──┘
                                                    (self-loop con MemorySaver)
```

### Protocolo WebSocket

El servidor y el cliente se comunican por WebSocket (`/ws/{session_id}`):

**Servidor → Cliente**

| `type` | Cuándo | Contenido |
|---|---|---|
| `question` | Inicio | Saludo + pregunta de tema |
| `status` | Durante operaciones lentas | Indicador de progreso |
| `equation` | Ecuación lista | `equation` + `explanation` |
| `papers` | Papers encontrados | Lista de papers + `templates` |
| `qa` | Ciclo Q&A | `last_answer`, `show_matrix`, `matrix` |
| `error` | Excepción | Mensaje de error |

**Cliente → Servidor**

| Etapa | Payload enviado |
|---|---|
| Tema | `{type, content: "texto libre"}` |
| Ecuación | `{type, content: "ecuación o confirmar", count: 5}` |
| Plantilla | `{type, content: "personalización", template_id: "benchmarking"}` |
| Q&A | `{type, content: "pregunta"}` |

---

## Estructura del proyecto

```
ResearchAgent-DataHack2026/
│
├── app/
│   ├── __init__.py
│   ├── state.py        # Paper TypedDict, MATRIX_TEMPLATES, ResearchState
│   ├── tools.py        # search_arxiv() y search_scholar() con datos bibliométricos
│   ├── agent.py        # 7 nodos LangGraph + MemorySaver + INITIAL_STATE
│   └── main.py         # FastAPI, WebSocket /ws/{session_id}, GET /api/download/xlsx/{id}
│
├── static/
│   └── index.html      # SPA: Tailwind CSS + marked.js + Clippy SVG
│
├── requirements.txt
└── README.md
```

### Módulos principales

**`app/state.py`** — define el estado compartido del grafo:
- `Paper` — TypedDict con 15 campos bibliométricos
- `MATRIX_TEMPLATES` — lista de 6 plantillas con id, nombre, icono, descripción y formato
- `ResearchState` — TypedDict con todo el estado de la sesión

**`app/tools.py`** — búsqueda en fuentes académicas:
- `search_arxiv(query, max_results)` — usa la API oficial de ArXiv; extrae PDF URL, categorías, journal_ref
- `search_scholar(query, max_results)` — usa `scholarly`; extrae citas, volumen, páginas, DOI

**`app/agent.py`** — grafo LangGraph de 7 nodos:
- Cada nodo que requiere input del usuario llama a `interrupt()` — pausa la ejecución del grafo y espera `Command(resume=valor)` para continuar
- La ecuación se genera con un prompt estructurado que produce grupos de sinónimos, operadores de campo y términos de exclusión

**`app/main.py`** — servidor FastAPI:
- WebSocket que ruta el `resume_value` según la etapa actual (string, dict con ecuación, dict con plantilla)
- Endpoint `GET /api/download/xlsx/{session_id}` — genera workbook con 3 hojas usando openpyxl

---

## Variables de entorno

| Variable | Default | Descripción |
|---|---|---|
| `OLLAMA_MODEL` | `llama3.1:8b` | Modelo Ollama a usar |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | URL del servidor Ollama |

Se pueden definir en un archivo `.env` en la raíz del proyecto o directamente al ejecutar:

```bash
OLLAMA_MODEL=qwen2.5:7b-instruct-q8_0 uv run uvicorn app.main:app --reload
```

---

## Fuentes de datos

| Fuente | Mecanismo | Datos disponibles |
|---|---|---|
| **ArXiv** | API oficial (`arxiv` library) | Título, autores, año, abstract, DOI, categorías, journal ref, PDF URL, Open Access |
| **Google Scholar** | Web scraping (`scholarly`) | Título, autores, año, abstract, DOI, citas, revista, volumen, número, páginas |

> **Nota sobre Google Scholar:** Scholar puede bloquear el scraping automático en algunas redes o tras muchas búsquedas. Si esto ocurre, los resultados de ArXiv siguen disponibles. Reintentar en unos minutos suele resolver el problema.

---

## Stack tecnológico

| Capa | Tecnología | Rol |
|---|---|---|
| **Orquestación** | LangGraph 0.2+ | Grafo de estados con `interrupt()` para pausas conversacionales y `MemorySaver` para persistencia |
| **LLM local** | Ollama + llama3.1:8b | Generación de ecuaciones, matrices y respuestas — sin API key, sin costo por token |
| **Backend** | FastAPI + WebSocket | Servidor asíncrono; enruta mensajes entre frontend y grafo |
| **Frontend** | Tailwind CSS + marked.js | SPA en un solo HTML; sin framework, sin build step |
| **Exportación** | openpyxl | Genera archivos .xlsx con 3 hojas estilizadas |
| **ArXiv** | `arxiv` library | Búsqueda con operadores booleanos y acceso directo a PDFs |
| **Scholar** | `scholarly` | Scraping de Google Scholar; citas y metadatos adicionales |

---

## Solución de problemas

**`ollama: command not found`**
Ollama está instalado pero no en el PATH. Úsalo con la ruta completa o reinicia la terminal después de instalarlo.

**Google Scholar devuelve error o sin resultados**
Scholar bloquea temporalmente el acceso automatizado. Los papers de ArXiv siguen disponibles. Espera unos minutos e intenta de nuevo.

**El LLM responde muy lento**
Usa un modelo más ligero (`llama3.1:8b` en lugar de variantes q8) o asegúrate de que Ollama está usando la GPU. Verifica con `ollama ps`.

**`ModuleNotFoundError`**
Asegúrate de ejecutar con `uv run` para usar el entorno virtual creado con `uv venv`, o instala las dependencias con `uv pip install -r requirements.txt`.

**La sesión se desconecta**
El WebSocket reconecta automáticamente. Al volver al mismo `session_id`, el grafo retoma el estado exacto donde lo dejaste.
