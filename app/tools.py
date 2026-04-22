import arxiv


def search_arxiv(query: str, max_results: int = 5) -> list:
    try:
        client = arxiv.Client()
        search = arxiv.Search(
            query=query,
            max_results=max_results,
            sort_by=arxiv.SortCriterion.Relevance,
        )
        papers = []
        for result in client.results(search):
            authors = [a.name for a in result.authors]
            abs_url = result.entry_id
            pdf_url = abs_url.replace("/abs/", "/pdf/") if abs_url else ""
            keywords = ", ".join(result.categories[:5]) if result.categories else ""
            journal = result.journal_ref or ""

            papers.append({
                "title": result.title,
                "authors": ", ".join(authors[:3]) + (" et al." if len(authors) > 3 else ""),
                "year": str(result.published.year),
                "abstract": result.summary[:500] + ("..." if len(result.summary) > 500 else ""),
                "url": abs_url,
                "pdf_url": pdf_url,
                "source": "ArXiv",
                "doi": result.doi or "",
                "journal": journal,
                "citations": "N/D",
                "keywords": keywords,
                "open_access": "Sí",
                "volume": "",
                "issue": "",
                "pages": "",
            })
        return papers
    except Exception as e:
        return [{
            "title": f"Error ArXiv: {str(e)[:120]}",
            "authors": "", "year": "N/D", "abstract": "",
            "url": "", "pdf_url": "", "source": "ArXiv", "doi": "",
            "journal": "", "citations": "", "keywords": "",
            "open_access": "N/D", "volume": "", "issue": "", "pages": "",
        }]


def search_scholar(query: str, max_results: int = 5) -> list:
    try:
        from scholarly import scholarly as gs

        papers = []
        count = 0
        for result in gs.search_pubs(query):
            if count >= max_results:
                break
            bib = result.get("bib", {})
            raw_authors = bib.get("author", ["Desconocido"])
            if isinstance(raw_authors, str):
                raw_authors = [raw_authors]
            authors = [str(a) for a in raw_authors]
            num_citations = result.get("num_citations", "N/D")
            journal = bib.get("venue", bib.get("journal", bib.get("booktitle", "")))

            papers.append({
                "title": bib.get("title", "Sin título"),
                "authors": ", ".join(authors[:3]) + (" et al." if len(authors) > 3 else ""),
                "year": str(bib.get("pub_year", "N/D")),
                "abstract": bib.get("abstract", "Sin resumen")[:500],
                "url": result.get("pub_url", result.get("eprint_url", "")),
                "pdf_url": result.get("eprint_url", ""),
                "source": "Google Scholar",
                "doi": bib.get("doi", ""),
                "journal": journal,
                "citations": str(num_citations),
                "keywords": "",
                "open_access": "N/D",
                "volume": str(bib.get("volume", "")),
                "issue": str(bib.get("number", "")),
                "pages": str(bib.get("pages", "")),
            })
            count += 1

        if not papers:
            papers.append({
                "title": "Sin resultados en Google Scholar",
                "authors": "", "year": "", "abstract": "Ajusta la ecuación de búsqueda.",
                "url": "", "pdf_url": "", "source": "Google Scholar", "doi": "",
                "journal": "", "citations": "", "keywords": "",
                "open_access": "N/D", "volume": "", "issue": "", "pages": "",
            })
        return papers

    except Exception as e:
        return [{
            "title": f"Google Scholar no disponible: {str(e)[:80]}",
            "authors": "", "year": "N/D",
            "abstract": "Google Scholar puede estar limitando el acceso automatizado.",
            "url": "", "pdf_url": "", "source": "Google Scholar", "doi": "",
            "journal": "", "citations": "N/D", "keywords": "",
            "open_access": "N/D", "volume": "", "issue": "", "pages": "",
        }]
