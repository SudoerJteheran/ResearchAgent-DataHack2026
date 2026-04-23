import re as _re
import arxiv


_ACCENT_MAP = str.maketrans(
    'áàâäéèêëíìîïóòôöúùûüñçýÁÀÂÄÉÈÊËÍÌÎÏÓÒÔÖÚÙÛÜÑÇÝ',
    'aaaaeeeeiiiioooouuuuncyAAAAEEEEIIIIOOOOUUUUNCY'
)


def _sanitize_for_arxiv(query: str) -> str:
    """Remove constructs that cause HTTP 400 on the ArXiv export API."""
    # Transliterate accented/special chars to ASCII
    q = query.translate(_ACCENT_MAP)
    # Drop any remaining non-ASCII bytes
    q = q.encode('ascii', 'ignore').decode('ascii')
    # Remove wildcard asterisks (not supported by ArXiv API)
    q = q.replace('*', '')
    # ArXiv uses ANDNOT, not NOT
    q = _re.sub(r'\bNOT\b', 'ANDNOT', q)
    # Strip characters that are not valid in ArXiv query syntax
    q = _re.sub(r'[^\w\s()"\'ANDORNOT:+\-]', ' ', q)
    q = _re.sub(r'\s+', ' ', q).strip()
    # Limit length and repair dangling operators / parentheses
    if len(q) > 250:
        q = q[:250]
        last = q.rfind(' ')
        if last > 120:
            q = q[:last]
        q = _re.sub(r'\s+(AND|OR|ANDNOT)\s*$', '', q).strip()
    opens = q.count('(') - q.count(')')
    if opens > 0:
        q += ')' * opens
    return q.strip() or 'research'


def search_arxiv(query: str, max_results: int = 5) -> list:
    try:
        client = arxiv.Client()
        search = arxiv.Search(
            query=_sanitize_for_arxiv(query),
            max_results=max_results,
            sort_by=arxiv.SortCriterion.Relevance,
        )
        papers = []
        for result in client.results(search):
            title = (result.title or "").strip()
            if not title:
                continue
            authors = [a.name for a in result.authors]
            abs_url = result.entry_id
            pdf_url = abs_url.replace("/abs/", "/pdf/") if abs_url else ""
            keywords = ", ".join(result.categories[:5]) if result.categories else ""
            journal = result.journal_ref or ""

            papers.append({
                "title": title,
                "authors": ", ".join(authors[:3]) + (" et al." if len(authors) > 3 else ""),
                "year": str(result.published.year),
                "abstract": result.summary[:500] + ("..." if len(result.summary) > 500 else ""),
                "url": abs_url,
                "pdf_url": pdf_url,
                "source": "ArXiv",
                "doi": result.doi or "",
                "journal": journal,
                "citations": "",
                "keywords": keywords,
                "open_access": "Sí",
                "volume": "",
                "issue": "",
                "pages": "",
            })
        return papers
    except Exception:
        return []


def search_scholar(query: str, max_results: int = 5) -> list:
    try:
        from scholarly import scholarly as gs

        papers = []
        count = 0
        for result in gs.search_pubs(query):
            if count >= max_results:
                break
            bib = result.get("bib", {})
            title = (bib.get("title") or "").strip()
            if not title:
                count += 1
                continue
            raw_authors = bib.get("author", ["Desconocido"])
            if isinstance(raw_authors, str):
                raw_authors = [raw_authors]
            authors = [str(a) for a in raw_authors]
            num_citations = result.get("num_citations", "")
            journal = bib.get("venue", bib.get("journal", bib.get("booktitle", "")))
            year_raw = bib.get("pub_year", "")
            year = str(year_raw) if year_raw and str(year_raw).isdigit() else ""

            papers.append({
                "title": title,
                "authors": ", ".join(authors[:3]) + (" et al." if len(authors) > 3 else ""),
                "year": year,
                "abstract": bib.get("abstract", "")[:500],
                "url": result.get("pub_url", result.get("eprint_url", "")),
                "pdf_url": result.get("eprint_url", ""),
                "source": "Google Scholar",
                "doi": bib.get("doi", ""),
                "journal": journal,
                "citations": str(num_citations) if num_citations != "" else "",
                "keywords": "",
                "open_access": "",
                "volume": str(bib.get("volume", "")),
                "issue": str(bib.get("number", "")),
                "pages": str(bib.get("pages", "")),
            })
            count += 1

        return papers

    except Exception:
        return []
