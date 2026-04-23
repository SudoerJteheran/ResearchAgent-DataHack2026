from typing import TypedDict, List


class Paper(TypedDict):
    title: str
    authors: str
    year: str
    abstract: str
    url: str
    pdf_url: str
    source: str
    doi: str
    journal: str
    citations: str
    keywords: str
    open_access: str
    volume: str
    issue: str
    pages: str


MATRIX_TEMPLATES = [
    {
        "id": "estado_arte",
        "name": "Estado del Arte",
        "icon": "🗺️",
        "description": "Panorama técnico de enfoques y soluciones existentes",
        "format": (
            "Tabla con columnas: Autores, Año, Título, Institución/País, "
            "Técnica o Algoritmo, Dataset utilizado, Métricas de evaluación, "
            "Resultados principales, Aportes al campo, Limitaciones, Citas, DOI"
        ),
    },
    {
        "id": "revision_sistematica",
        "name": "Revisión Sistemática",
        "icon": "🔬",
        "description": "Síntesis rigurosa tipo PRISMA con niveles de evidencia",
        "format": (
            "Tabla con columnas: Autores, Año, Título, Revista/Fuente, País, "
            "Tipo de estudio, Muestra o Datos, Metodología, Resultados clave, "
            "Nivel de evidencia, Riesgo de sesgo, Citas recibidas, DOI"
        ),
    },
    {
        "id": "benchmarking",
        "name": "Benchmarking Técnico",
        "icon": "📊",
        "description": "Comparación cuantitativa de modelos y métricas de desempeño",
        "format": (
            "Tabla con columnas: Autores, Año, Modelo o Método, Dataset, "
            "Accuracy, Precision, Recall, F1-Score, AUC-ROC, "
            "Tiempo o Hardware, Código disponible (Sí/No), Citas, DOI"
        ),
    },
]


class ResearchState(TypedDict):
    stage: str
    research_needs: str
    search_equation: str
    equation_explanation: str
    paper_count: int
    papers: List[Paper]
    matrix_template: str
    matrix_format: str
    matrix: str
    hypotheses: List[dict]
    chat_history: List[dict]
    last_answer: str
