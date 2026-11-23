from fastapi import APIRouter, Query, Depends, HTTPException
from typing import List, Optional
try:
    from models.metadata_model import MetadataResponse
except (ImportError, AttributeError):
    from services.ms1_retrieval.models.metadata_model import MetadataResponse
from services.metadata_service import MetadataService

router = APIRouter(
    prefix="/metadata",
    tags=["Metadata Retrieval"]
)

def get_metadata_service() -> MetadataService:
    return MetadataService()

@router.get("/search", response_model=List[MetadataResponse])
async def search_metadata(
    query: str = Query(..., description="Término de búsqueda (ej. 'Machine Learning')"),
    source: Optional[str] = Query(None, description="Fuente específica (crossref, openalex, semanticscholar, europepmc, unpaywall) o vacío para todas"),
    limit: int = Query(5, description="Límite de resultados por fuente (default 5)"),
    svc: MetadataService = Depends(get_metadata_service)
):
    """
    Busca metadatos de literatura científica en fuentes externas concurrentes.
    """
    return await svc.search_metadata(query, source, limit)

@router.get("/doi/{doi:path}", response_model=List[MetadataResponse])
async def search_metadata_by_doi(
    doi: str,
    source: Optional[str] = Query(None, description="Fuente específica o vacío para todas"),
    svc: MetadataService = Depends(get_metadata_service)
):
    """
    Recupera metadatos exactos a partir de un DOI específico.
    """
    results = await svc.get_metadata_by_doi(doi, source)
    if not results:
        raise HTTPException(status_code=404, detail="No se encontraron metadatos para el DOI especificado")
    return results

@router.get("/exact_title", response_model=Optional[MetadataResponse])
async def search_metadata_by_exact_title(
    title: str = Query(..., description="Título exacto de la publicación (ej. 'Attention Is All You Need')"),
    svc: MetadataService = Depends(get_metadata_service)
):
    """
    Coincidencia exacta de título: Cuenta con un endpoint específico para buscar
    un artículo por su título exacto (title) en Semantic Scholar (/paper/search/match),
    ideal cuando se conoce el nombre completo de la publicación.
    """
    result = await svc.get_metadata_by_exact_title(title)
    if not result:
        raise HTTPException(status_code=404, detail="No se encontró coincidencia exacta de título en Semantic Scholar")
    return result

