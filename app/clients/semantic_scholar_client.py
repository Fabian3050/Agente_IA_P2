import httpx
import os
import urllib.parse
from typing import List, Optional
from app.models.metadata_model import MetadataResponse

SEMANTIC_SCHOLAR_FIELDS = "title,authors,year,externalIds,url,abstract,s2FieldsOfStudy,openAccessPdf"

def _get_headers() -> dict:
    headers = {"User-Agent": "AgenteIA-DSpace/3.0 (mailto:agente_ia@usach.cl)"}
    api_key = os.getenv("SEMANTIC_SCHOLAR_API_KEY")
    if api_key:
        headers["x-api-key"] = api_key
    return headers

def _parse_semantic_scholar_item(item: dict) -> MetadataResponse:
    title = item.get("title") or "No title"
    authors = [auth.get("name", "") for auth in item.get("authors", []) if auth and auth.get("name")]
    
    external_ids = item.get("externalIds") or {}
    doi = external_ids.get("DOI")
    year = item.get("year")
    item_url = item.get("url")
    abstract = item.get("abstract")
    
    s2FieldsOfStudy = item.get("s2FieldsOfStudy") or []
    keywords = []
    for f in s2FieldsOfStudy:
        if isinstance(f, dict) and f.get("category"):
            keywords.append(f.get("category"))
        elif isinstance(f, str):
            keywords.append(f)
            
    open_access = item.get("openAccessPdf") or {}
    oa_status = open_access.get("status") if isinstance(open_access, dict) else None

    return MetadataResponse(
        title=title,
        authors=authors,
        doi=doi,
        year=year,
        source="semanticscholar",
        url=item_url,
        abstract=abstract,
        keywords=keywords if keywords else None,
        author_keywords=keywords if keywords else None,
        s2FieldsOfStudy=s2FieldsOfStudy,
        oa_status=oa_status
    )

async def get_by_exact_title_semantic_scholar(title: str, client: Optional[httpx.AsyncClient] = None) -> Optional[MetadataResponse]:
    """
    Coincidencia exacta de título: Cuenta con un endpoint específico para buscar
    un artículo por su título exacto (/paper/search/match), ideal cuando se conoce
    el nombre completo de la publicación científica.
    """
    if not title or len(title.strip()) < 4:
        return None

    clean_title = title.strip()
    headers = _get_headers()

    async def _execute_query(http_client: httpx.AsyncClient) -> Optional[MetadataResponse]:
        # 1. Endpoint específico de coincidencia de título: /paper/search/match
        try:
            url_match = "https://api.semanticscholar.org/graph/v1/paper/search/match"
            params = {
                "query": clean_title,
                "fields": SEMANTIC_SCHOLAR_FIELDS
            }
            response = await http_client.get(url_match, params=params, headers=headers, timeout=12.0)
            if response.status_code == 200:
                data = response.json()
                item = None
                if isinstance(data, dict):
                    if "data" in data and isinstance(data["data"], list) and len(data["data"]) > 0:
                        item = data["data"][0]
                    elif "title" in data or "paperId" in data:
                        item = data
                if item and item.get("title"):
                    return _parse_semantic_scholar_item(item)
            elif response.status_code == 404:
                # No se encontró coincidencia directa en /search/match
                pass
        except Exception as e:
            print(f"[SemanticScholar] Error en /paper/search/match por título exacto: {e}")

        # 2. Endpoint complementario de búsqueda directa por prefijo de título: /paper/title:{title}
        try:
            encoded_title = urllib.parse.quote(clean_title)
            url_title = f"https://api.semanticscholar.org/graph/v1/paper/title:{encoded_title}"
            params = {"fields": SEMANTIC_SCHOLAR_FIELDS}
            response = await http_client.get(url_title, params=params, headers=headers, timeout=12.0)
            if response.status_code == 200:
                item = response.json()
                if item and item.get("title"):
                    return _parse_semantic_scholar_item(item)
        except Exception as e:
            print(f"[SemanticScholar] Error en /paper/title por título exacto: {e}")

        return None

    if client:
        return await _execute_query(client)
    else:
        async with httpx.AsyncClient() as new_client:
            return await _execute_query(new_client)

# Alias para compatibilidad
get_by_title_semantic_scholar = get_by_exact_title_semantic_scholar

async def search_semantic_scholar(query: str, limit: int = 5) -> List[MetadataResponse]:
    url = "https://api.semanticscholar.org/graph/v1/paper/search"
    params = {
        "query": query, 
        "limit": limit,
        "fields": SEMANTIC_SCHOLAR_FIELDS
    }
    results = []
    headers = _get_headers()
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, params=params, headers=headers, timeout=10.0)
            response.raise_for_status()
            data = response.json()
            items = data.get("data", [])
            
            for item in items:
                results.append(_parse_semantic_scholar_item(item))
        except Exception as e:
            print(f"Error fetching from Semantic Scholar: {e}")
            
    return results

async def get_by_doi_semantic_scholar(doi: str) -> Optional[MetadataResponse]:
    url = f"https://api.semanticscholar.org/graph/v1/paper/DOI:{doi}"
    params = {
        "fields": SEMANTIC_SCHOLAR_FIELDS
    }
    headers = _get_headers()
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, params=params, headers=headers, timeout=10.0)
            if response.status_code == 404:
                return None
            response.raise_for_status()
            item = response.json()
            return _parse_semantic_scholar_item(item)
        except Exception as e:
            print(f"Error fetching from Semantic Scholar by DOI: {e}")
            
    return None

async def get_doi_by_title_and_abstract_semantic_scholar(title: Optional[str] = None, abstract: Optional[str] = None) -> Optional[str]:
    if not title and not abstract:
        return None
    
    parts = []
    if title:
        parts.append(title)
    if abstract:
        parts.append(abstract)
        
    query = (" ".join(parts))[:300]
    url = "https://api.semanticscholar.org/graph/v1/paper/search"
    params = {
        "query": query, 
        "limit": 1,
        "fields": "externalIds"
    }
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, params=params, timeout=10.0)
            response.raise_for_status()
            data = response.json()
            items = data.get("data", [])
            if items:
                external_ids = items[0].get("externalIds", {})
                return external_ids.get("DOI")
        except Exception as e:
            print(f"Error fetching DOI from Semantic Scholar by title and abstract: {e}")
    return None
