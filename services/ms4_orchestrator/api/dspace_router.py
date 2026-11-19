from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from typing import Optional

try:
    from services.dspace_service import DSpaceService
except ImportError:
    from services.ms4_orchestrator.services.dspace_service import DSpaceService

try:
    from common.database import get_db
except ImportError:
    from services.common.database import get_db

try:
    from models import DSpaceMetricsHistory, DSpaceEnrichmentQueue
except ImportError:
    from services.ms4_orchestrator.models import DSpaceMetricsHistory, DSpaceEnrichmentQueue

router = APIRouter(
    prefix="/dspace",
    tags=["DSpace Integration"]
)

# Dependencia de FastAPI para inyectar el servicio
def get_dspace_service():
    return DSpaceService()

@router.get("/items")
async def get_items(
    page: int = Query(0, description="Número de página (índice base 0)"),
    size: int = Query(20, description="Cantidad de registros de metadatos por página"),
    use_cache: bool = Query(True, description="Usar caché local en disco para no saturar la API y consumir datos más rápido"),
    dspace_service: DSpaceService = Depends(get_dspace_service)
):
    """
    Obtiene la lista de publicaciones desde DSpace.
    Devuelve estrictamente los metadatos de los registros, no archivos adjuntos (PDFs).
    Implementa caché en disco para consumir datos más rápido.
    """
    try:
        return await dspace_service.get_all_items(page=page, size=size, use_cache=use_cache)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error comunicándose con DSpace: {str(e)}")

@router.get("/items/{item_id}")
async def get_item_metadata(
    item_id: str,
    use_cache: bool = Query(True, description="Usar caché local para respuesta inmediata"),
    dspace_service: DSpaceService = Depends(get_dspace_service)
):
    """
    Obtiene los metadatos completos de un registro individual en base a su UUID.
    Aprovecha la caché local para obtener el registro instantáneamente.
    """
    try:
        return await dspace_service.get_metadata(item_id, use_cache=use_cache)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error obteniendo el ítem {item_id}: {str(e)}")

@router.get("/count-missing")
async def count_missing(
    save_to_db: bool = Query(False, description="Guardar snapshot de métricas en histórico y poblar la cola de enriquecimiento en BD"),
    use_cache: bool = Query(True, description="Usar caché local en disco para acelerar el escaneo"),
    dspace_service: DSpaceService = Depends(get_dspace_service),
    db: Session = Depends(get_db)
):
    """
    Cuenta los items que no tienen abstract ni DOI dentro de valid_resource_types.
    Opcionalmente guarda el histórico de métricas y la cola de enriquecimiento en la base de datos.
    Aprovecha la caché local en disco para un procesamiento ultrarrápido.
    """
    try:
        return await dspace_service.count_missing_metadata_optimized(save_to_db=save_to_db, db=db, use_cache=use_cache)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error contando items: {str(e)}")

@router.get("/cache/stats")
def get_cache_stats(
    dspace_service: DSpaceService = Depends(get_dspace_service)
):
    """
    Retorna métricas y estadísticas sobre los archivos y tamaño de la caché de DSpace en disco.
    """
    return dspace_service.get_cache_stats()

@router.delete("/cache")
def clear_cache(
    clear_pages: bool = Query(True, description="Eliminar páginas cacheadas"),
    clear_items: bool = Query(True, description="Eliminar ítems individuales cacheados"),
    dspace_service: DSpaceService = Depends(get_dspace_service)
):
    """
    Limpia los archivos de la caché en disco para forzar una consulta fresca a la API de DSpace.
    """
    return dspace_service.clear_cache(clear_pages=clear_pages, clear_items=clear_items)

@router.get("/metrics-history")
def get_metrics_history(
    limit: int = Query(30, description="Cantidad máxima de registros históricos a retornar"),
    db: Session = Depends(get_db)
):
    """
    Retorna el histórico cronológico de métricas del repositorio para alimentar dashboards.
    """
    from models import DSpaceMetricsHistory
    records = db.query(DSpaceMetricsHistory).order_by(DSpaceMetricsHistory.fecha.desc()).limit(limit).all()
    return records

def calculate_record_completitud(i: DSpaceEnrichmentQueue):
    """
    Calcula el porcentaje de completitud real (0-100%) sobre los 6 metadatos enriquecidos objetivo:
    1. Fuente de financiamiento
    2. Resumen (abstract)
    3. Palabras clave
    4. Área OCDE
    5. Área ODS
    6. Derechos de acceso
    """
    rec_meta = i.metadatos_recuperados or {}

    # 1. Fuente de financiamiento
    has_funding = bool(i.fuente_financiamiento) or bool(rec_meta.get("funding"))

    # 2. Resumen
    has_abstract = bool(i.abstract_enriquecido and len(str(i.abstract_enriquecido).strip()) > 10) or \
                   bool(i.resumen_original and len(str(i.resumen_original).strip()) > 10) or \
                   bool(rec_meta.get("abstract") and len(str(rec_meta.get("abstract")).strip()) > 10)

    # 3. Palabras clave
    has_keywords = bool(i.palabras_clave) or bool(rec_meta.get("keywords"))

    # 4. Área OCDE
    has_ocde = bool(i.area_ocde) or bool(rec_meta.get("area_ocde"))

    # 5. Área ODS
    has_ods = bool(i.area_ods) or bool(rec_meta.get("area_ods"))

    # 6. Derechos de acceso
    access_val = str(i.derechos_acceso or rec_meta.get("access_rights") or rec_meta.get("derechos_acceso") or "").strip().lower()
    has_access = bool(access_val and access_val not in ["null", "none", "undefined", ""])

    count_post = sum([has_funding, has_abstract, has_keywords, has_ocde, has_ods, has_access])
    completitud = round((count_post / 6.0) * 100)

    # Pre-enriquecimiento (estado original antes de procesar)
    tf = (i.tipo_falencia or "").upper()
    had_abstract = bool(i.resumen_original and len(str(i.resumen_original).strip()) > 10) or \
                   (bool(tf) and "SIN_ABSTRACT" not in tf and "SIN_DOI_NI_ABSTRACT" not in tf and "SIN_ABSTRACT_CON_DOI" not in tf)
    had_keywords = bool(tf) and "SIN_PALABRAS_CLAVE" not in tf
    had_funding = bool(tf) and "SIN_FINANCIAMIENTO" not in tf
    had_access = (bool(access_val) and "SIN_DERECHOS_ACCESO" not in tf) or (bool(tf) and "SIN_DERECHOS_ACCESO" not in tf)
    had_ocde = False
    had_ods = False

    count_pre = sum([had_funding, had_abstract, had_keywords, had_ocde, had_ods, had_access])
    completitud_pre = min(completitud, round((count_pre / 6.0) * 100))

    return completitud, completitud_pre

@router.get("/enrichment-queue")
def get_enrichment_queue(
    estado: Optional[str] = Query(None, description="Filtrar por estado: PENDIENTE, EN_PROCESO, ENRIQUECIDO, NO_ENCONTRADO, ERROR, SINCRONIZADO_DSPACE"),
    tipo_falencia: Optional[str] = Query(None, description="Filtrar por falencia: SIN_ABSTRACT_CON_DOI, SIN_DOI_NI_ABSTRACT, etc."),
    q: Optional[str] = Query(None, description="Búsqueda por título, DOI o UUID"),
    page: int = Query(0, ge=0, description="Número de página"),
    size: int = Query(50, ge=1, le=20000, description="Cantidad de registros por página"),
    db: Session = Depends(get_db)
):
    """
    Retorna publicaciones en la cola de enriquecimiento con filtros y paginación para el dashboard.
    """
    from sqlalchemy import or_
    query = db.query(DSpaceEnrichmentQueue)
    if estado:
        if "," in estado:
            estados_list = [e.strip() for e in estado.split(",") if e.strip()]
            query = query.filter(DSpaceEnrichmentQueue.estado.in_(estados_list))
        else:
            query = query.filter(DSpaceEnrichmentQueue.estado == estado)
    if tipo_falencia:
        query = query.filter(DSpaceEnrichmentQueue.tipo_falencia.ilike(f"%{tipo_falencia}%"))
    if q:
        query = query.filter(
            or_(
                DSpaceEnrichmentQueue.titulo.ilike(f"%{q}%"),
                DSpaceEnrichmentQueue.doi.ilike(f"%{q}%"),
                DSpaceEnrichmentQueue.dspace_uuid.ilike(f"%{q}%")
            )
        )

    total = query.count()
    items = query.order_by(DSpaceEnrichmentQueue.id.asc()).offset(page * size).limit(size).all()
    serialized_items = []
    for i in items:
        comp, comp_pre = calculate_record_completitud(i)
        serialized_items.append({
            "id": i.id,
            "dspace_uuid": i.dspace_uuid,
            "uuid_dspace": i.dspace_uuid,
            "doi": i.doi,
            "titulo": i.titulo or (f"Publicación (DOI: {i.doi})" if i.doi else f"Registro DSpace #{i.id}"),
            "title": i.titulo or (f"Publicación (DOI: {i.doi})" if i.doi else f"Registro DSpace #{i.id}"),
            "tipo_recurso": i.tipo_recurso,
            "tipo_falencia": i.tipo_falencia,
            "estado": i.estado,
            "completitud": comp,
            "completitud_pre": comp_pre,
            "fuente_enriquecimiento": i.fuente_enriquecimiento,
            "abstract_enriquecido": i.abstract_enriquecido,
            "palabras_clave": i.palabras_clave,
            "fuente_financiamiento": i.fuente_financiamiento,
            "derechos_acceso": i.derechos_acceso,
            "licencia": getattr(i, "licencia", None) or (i.metadatos_recuperados.get("license") if i.metadatos_recuperados else None),
            "area_ocde": i.area_ocde,
            "area_ods": i.area_ods,
            "metadatos_recuperados": i.metadatos_recuperados or (
                {
                    "abstract": i.abstract_enriquecido,
                    "keywords": i.palabras_clave,
                    "funding": i.fuente_financiamiento,
                    "access_rights": i.derechos_acceso,
                    "license": getattr(i, "licencia", None),
                    "doi": i.doi,
                    "sources": [i.fuente_enriquecimiento] if i.fuente_enriquecimiento else [],
                    "area_ocde": i.area_ocde,
                    "area_ods": i.area_ods,
                } if (i.abstract_enriquecido or i.palabras_clave or i.fuente_financiamiento or i.derechos_acceso or getattr(i, "licencia", None) or i.area_ocde or i.area_ods) else None
            ),
            "resumen_original": i.resumen_original,
            "created_at": i.created_at.isoformat() if i.created_at else None,
            "updated_at": i.updated_at.isoformat() if i.updated_at else None
        })

    return {
        "total": total,
        "page": page,
        "size": size,
        "items": serialized_items
    }

@router.get("/enrichment-queue/stats")
def get_enrichment_queue_stats(
    db: Session = Depends(get_db)
):
    """
    Retorna estadísticas agregadas de la cola de enriquecimiento agrupadas por estado para los KPIs del Dashboard.
    """
    from models import DSpaceEnrichmentQueue
    from sqlalchemy import func
    stats = db.query(DSpaceEnrichmentQueue.estado, func.count(DSpaceEnrichmentQueue.id)).group_by(DSpaceEnrichmentQueue.estado).all()
    total = db.query(func.count(DSpaceEnrichmentQueue.id)).scalar() or 0
    return {
        "total_en_cola": total,
        "por_estado": {estado: count for estado, count in stats}
    }

@router.post("/enrich/{item_id}")
async def enrich_item(
    item_id: int,
    classify_with_ai: bool = Query(True, description="Ejecutar clasificación temática OCDE y ODS con IA (Ollama)"),
    db: Session = Depends(get_db)
):
    """
    Enriquece un ítem individual de la cola por su ID.
    Recupera abstract, keywords, financiamiento y derechos desde fuentes académicas,
    y opcionalmente clasifica en áreas OCDE y ODS usando el LLM (Ollama).
    """
    from services.enrichment_service import EnrichmentService
    service = EnrichmentService()
    resultado = await service.enrich_item_by_id(item_id, db, classify_with_ai=classify_with_ai)
    if not resultado:
        raise HTTPException(status_code=404, detail=f"No se encontró el registro con ID {item_id} en la cola de enriquecimiento.")
    return resultado

@router.post("/enrich-by-uuid/{dspace_uuid}")
async def enrich_item_by_uuid(
    dspace_uuid: str,
    classify_with_ai: bool = Query(True, description="Ejecutar clasificación temática OCDE y ODS con IA (Ollama)"),
    db: Session = Depends(get_db)
):
    """
    Enriquece un ítem individual de la cola por su UUID de DSpace.
    """
    from services.enrichment_service import EnrichmentService
    service = EnrichmentService()
    resultado = await service.enrich_item_by_uuid(dspace_uuid, db, classify_with_ai=classify_with_ai)
    if not resultado:
        raise HTTPException(status_code=404, detail=f"No se encontró el registro con UUID {dspace_uuid} en la cola de enriquecimiento.")
    return resultado

@router.post("/enrich-next")
async def enrich_next_batch(
    limit: int = Query(1, ge=1, le=50, description="Cantidad de registros pendientes a enriquecer en este lote"),
    classify_with_ai: bool = Query(True, description="Ejecutar clasificación temática OCDE y ODS con IA (Ollama)"),
    db: Session = Depends(get_db)
):
    """
    Toma los siguientes N registros en estado PENDIENTE de la cola y ejecuta el pipeline de enriquecimiento.
    Ideal para procesar y probar en lotes controlados (1, 5, 10 ítems).
    """
    from services.enrichment_service import EnrichmentService
    service = EnrichmentService()
    return await service.enrich_batch(limit=limit, estado_filtro="PENDIENTE", classify_with_ai=classify_with_ai, db=db)

@router.post("/generate-vriic-sample")
async def generate_vriic_sample(
    sample_size: int = Query(35, ge=5, le=50, description="Cantidad de publicaciones clasificadas para la muestra (alrededor de 30 a 40)"),
    output_filename: str = Query("muestra_clasificaciones_vriic.xlsx", description="Nombre del archivo Excel a generar en la raíz del proyecto"),
    force_reclassify: bool = Query(False, description="Si es True, fuerza la reclasificación con IA ignorando y sobrescribiendo las previas"),
    db: Session = Depends(get_db)
):
    """
    Genera una muestra de 30 a 40 publicaciones clasificadas (OCDE y ODS)
    a partir de registros de dspace_enrichment_queue con título y resumen original.
    Guarda las clasificaciones en la base de datos y exporta el archivo Excel en la raíz del proyecto para validación con la VRIIC.
    Si force_reclassify=True, vuelve a ejecutar el LLM en todos los ítems de la muestra.
    """
    from services.enrichment_service import EnrichmentService
    service = EnrichmentService()
    try:
        return await service.generate_vriic_sample(
            db=db,
            sample_size=sample_size,
            output_filename=output_filename,
            force_reclassify=force_reclassify
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generando la muestra VRIIC: {str(e)}")

@router.post("/reset-classifications")
def reset_classifications(
    item_id: Optional[int] = Query(None, description="ID numérico del registro específico a resetear"),
    dspace_uuid: Optional[str] = Query(None, description="UUID de DSpace específico a resetear"),
    reset_all: bool = Query(False, description="Si es True, elimina las clasificaciones de TODOS los registros que tengan áreas asignadas"),
    db: Session = Depends(get_db)
):
    """
    Elimina las clasificaciones realizadas (OCDE y ODS) en 'dspace_enrichment_queue' 
    y restablece su estado a PENDIENTE o ENRIQUECIDO_FUENTES para poder volver a clasificarlas.
    """
    from services.enrichment_service import EnrichmentService
    service = EnrichmentService()
    return service.reset_classifications(db=db, item_id=item_id, dspace_uuid=dspace_uuid, reset_all=reset_all)

@router.get("/download-vriic-sample")
def download_vriic_sample(
    filename: str = Query("muestra_clasificaciones_vriic.xlsx", description="Nombre del archivo a descargar")
):
    """
    Descarga directamente el archivo Excel generado para la validación de la VRIIC.
    """
    import os
    from fastapi.responses import FileResponse
    file_path = os.path.abspath(filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail=f"El archivo '{filename}' no existe aún. Ejecuta primero POST /dspace/generate-vriic-sample.")
    return FileResponse(
        path=file_path,
        filename=filename,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )