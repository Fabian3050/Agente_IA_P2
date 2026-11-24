import asyncio
import os
import uuid
from sqlalchemy import func, and_, case
from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session

try:
    from models import DSpaceEnrichmentQueue
    from clients.ms_clients import MS1Client, MS2Client
    from services.dspace_service import normalize_license
except ImportError:
    from services.ms4_orchestrator.models import DSpaceEnrichmentQueue
    from services.ms4_orchestrator.clients.ms_clients import MS1Client, MS2Client
    from services.ms4_orchestrator.services.dspace_service import normalize_license

class EnrichmentService:
    """
    Servicio encargado de enriquecer las publicaciones de la cola DSpaceEnrichmentQueue.
    Fase 1: Consulta a fuentes académicas (OpenAlex, CrossRef, Semantic Scholar, Europe PMC, etc.)
            para recuperar abstract, palabras clave, fuentes de financiamiento y derechos de acceso.
    Fase 2: Clasificación temática con IA (Ollama / LLaMA 3.2) para asignar áreas OCDE y ODS.
    """

    def __init__(self):
        self.ms1_client = MS1Client()
        self.ms2_client = MS2Client()

    async def enrich_item(self, item: DSpaceEnrichmentQueue, db: Session, classify_with_ai: bool = True) -> Dict[str, Any]:
        """
        Ejecuta el pipeline completo de enriquecimiento para un registro individual.
        """
        item.estado = "EN_PROCESO"
        item.intentos += 1
        item.updated_at = datetime.utcnow()
        db.commit()

        fuentes_utilizadas = set()
        abstract_encontrado: Optional[str] = None
        keywords_acumuladas = set()
        financiamiento_acumulado = set()
        derechos_acceso: Optional[str] = getattr(item, "derechos_acceso", None)
        licencia_encontrada: Optional[str] = getattr(item, "licencia", None)
        doi_encontrado: Optional[str] = item.doi
        raw_responses: List[Dict[str, Any]] = []

        t_start = datetime.utcnow()
        try:
            # ----------------------------------------------------
            # FASE 1: Búsqueda en Fuentes Académicas vía MS1
            # ----------------------------------------------------
            try:
                item_uuid = uuid.UUID(str(item.dspace_uuid))
            except Exception:
                item_uuid = uuid.uuid5(uuid.NAMESPACE_DNS, str(item.dspace_uuid or item.id))

            max_score = 0.0
            try:
                res_ms1 = await self.ms1_client.retrieve(item_id=item_uuid, doi=item.doi, title=item.titulo)
                consolidated = res_ms1.get("consolidated", {})
                best_source = res_ms1.get("best_source")
                max_score = float(res_ms1.get("max_score", 0.0) or 0.0)
                if consolidated.get("abstract"):
                    abstract_encontrado = str(consolidated["abstract"]).strip()
                if consolidated.get("author_keywords"):
                    kw_list = consolidated["author_keywords"]
                    if isinstance(kw_list, list):
                        keywords_acumuladas.update([str(k).strip() for k in kw_list if str(k).strip()])
                    elif isinstance(kw_list, str):
                        keywords_acumuladas.add(kw_list.strip())
                if consolidated.get("funding_agency"):
                    financiamiento_acumulado.add(str(consolidated["funding_agency"]).strip())
                if consolidated.get("oa_status"):
                    derechos_acceso = str(consolidated["oa_status"]).strip()
                if consolidated.get("license"):
                    licencia_encontrada = normalize_license(str(consolidated["license"]).strip())
                elif res_ms1.get("license"):
                    licencia_encontrada = normalize_license(str(res_ms1["license"]).strip())
                if consolidated.get("doi") and not item.doi:
                    doi_encontrado = str(consolidated["doi"]).strip()
                if best_source:
                    fuentes_utilizadas.add(best_source)
                if consolidated.get("abstract_source"):
                    fuentes_utilizadas.add(consolidated["abstract_source"])
            except Exception as e_ms1:
                print(f"[EnrichmentService] Error consultando MS1: {e_ms1}")

            # -------------------------------------------------------------------------
            # FASE 1.1: Coincidencia Exacta de Título en Semantic Scholar (Fallback/Boost)
            # Si aún no tenemos abstract y se conoce el título completo de la publicación
            # -------------------------------------------------------------------------
            if not abstract_encontrado and item.titulo and len(item.titulo.strip()) > 5:
                try:
                    import httpx
                    clean_t = item.titulo.strip()
                    url_ss = "https://api.semanticscholar.org/graph/v1/paper/search/match"
                    async with httpx.AsyncClient() as http_c:
                        resp_ss = await http_c.get(
                            url_ss,
                            params={"query": clean_t, "fields": "title,authors,year,externalIds,url,abstract,s2FieldsOfStudy,openAccessPdf"},
                            headers={"User-Agent": "AgenteIA-DSpace/3.0 (mailto:agente_ia@usach.cl)"},
                            timeout=10.0
                        )
                        if resp_ss.status_code == 200:
                            data_ss = resp_ss.json()
                            item_ss = data_ss.get("data", [data_ss])[0] if isinstance(data_ss.get("data"), list) and data_ss.get("data") else data_ss
                            if item_ss and item_ss.get("abstract"):
                                abstract_encontrado = str(item_ss["abstract"]).strip()
                                fuentes_utilizadas.add("semanticscholar")
                                if not item.doi and item_ss.get("externalIds", {}).get("DOI"):
                                    doi_encontrado = item_ss["externalIds"]["DOI"]
                                if item_ss.get("s2FieldsOfStudy"):
                                    for f in item_ss["s2FieldsOfStudy"]:
                                        if isinstance(f, dict) and f.get("category"):
                                            keywords_acumuladas.add(f["category"])
                except Exception as e_ss_fb:
                    print(f"[EnrichmentService] Nota: Fallback coincidencia exacta Semantic Scholar no disponible: {e_ss_fb}")

            # ----------------------------------------------------
            # FASE 2: Clasificación Temática con IA vía MS2
            # ----------------------------------------------------
            if classify_with_ai:
                abstract_para_llm = abstract_encontrado or item.abstract_enriquecido or item.resumen_original
                if item.titulo or abstract_para_llm:
                    try:
                        res_ms2 = await self.ms2_client.classify(
                            item_id=item_uuid,
                            title=item.titulo,
                            abstract=abstract_para_llm,
                            keywords=", ".join(keywords_acumuladas) if keywords_acumuladas else None
                        )
                        if res_ms2.get("area_ocde"):
                            item.area_ocde = res_ms2["area_ocde"] if isinstance(res_ms2["area_ocde"], list) else [res_ms2["area_ocde"]]
                        if res_ms2.get("area_ods"):
                            item.area_ods = res_ms2["area_ods"] if isinstance(res_ms2["area_ods"], list) else [res_ms2["area_ods"]]
                    except Exception as e_ms2:
                        print(f"[EnrichmentService] Error consultando MS2: {e_ms2}")

            # Actualizar campos consolidados del registro
            if abstract_encontrado:
                item.abstract_enriquecido = abstract_encontrado
            if keywords_acumuladas:
                item.palabras_clave = list(sorted(keywords_acumuladas))
            if financiamiento_acumulado:
                item.fuente_financiamiento = list(sorted(financiamiento_acumulado))
            if derechos_acceso:
                item.derechos_acceso = derechos_acceso
            if licencia_encontrada:
                item.licencia = licencia_encontrada
            if doi_encontrado and not item.doi:
                item.doi = doi_encontrado
            if fuentes_utilizadas:
                item.fuente_enriquecimiento = ", ".join(sorted(fuentes_utilizadas))

            # Calcular tiempo total de ejecución (MS1 + MS2)
            t_total_seconds = max(0.05, (datetime.utcnow() - t_start).total_seconds())
            t_total_ms = int(t_total_seconds * 1000)

            # Incorporar metadatos enriquecidos en el campo 'metadatos_recuperados' de dspace_enrichment_queue
            metadatos_recuperados_payload = {
                "abstract": item.abstract_enriquecido,
                "keywords": item.palabras_clave,
                "funding": item.fuente_financiamiento,
                "access_rights": item.derechos_acceso,
                "license": getattr(item, "licencia", None) or licencia_encontrada,
                "doi": item.doi,
                "sources": list(sorted(fuentes_utilizadas)) if fuentes_utilizadas else [],
                "area_ocde": item.area_ocde,
                "area_ods": item.area_ods,
                "max_score": max_score,
                "tiempo_ejecucion_ms": t_total_ms,
                "tiempo_ejecucion_segundos": round(t_total_seconds, 2),
                "recovered_at": datetime.utcnow().isoformat()
            }
            if 'res_ms1' in locals() and isinstance(res_ms1, dict):
                if res_ms1.get("best_source"):
                    metadatos_recuperados_payload["best_source"] = res_ms1.get("best_source")
                if res_ms1.get("candidate_matches"):
                    metadatos_recuperados_payload["candidate_matches"] = res_ms1.get("candidate_matches")
                elif res_ms1.get("consolidated"):
                    metadatos_recuperados_payload["consolidated"] = res_ms1.get("consolidated")

            item.metadatos_recuperados = metadatos_recuperados_payload

            # Criterio de validación manual:
            # Si tiene coincidencias pero el match score es menor al 80% (0.8), requiere validación manual
            if max_score > 0.0 and max_score < 0.8:
                item.estado = "PENDIENTE_VALIDACION"
            elif abstract_encontrado or keywords_acumuladas or item.area_ocde or item.area_ods or item.abstract_enriquecido:
                item.estado = "ENRIQUECIDO"
            else:
                item.estado = "EN_PROCESO"

            item.mensaje_error = None

        except Exception as e:
            item.estado = "ERROR"
            item.mensaje_error = str(e)
            print(f"Error general enriqueciendo item {item.id} ({item.dspace_uuid}): {e}")

        item.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(item)

        return {
            "id": item.id,
            "dspace_uuid": item.dspace_uuid,
            "doi": item.doi,
            "titulo": item.titulo,
            "estado": item.estado,
            "fuente_enriquecimiento": item.fuente_enriquecimiento,
            "tiene_abstract": bool(item.abstract_enriquecido),
            "abstract_enriquecido": item.abstract_enriquecido,
            "palabras_clave": item.palabras_clave,
            "fuente_financiamiento": item.fuente_financiamiento,
            "derechos_acceso": item.derechos_acceso,
            "licencia": getattr(item, "licencia", None),
            "area_ocde": item.area_ocde,
            "area_ods": item.area_ods,
            "metadatos_recuperados": item.metadatos_recuperados,
            "mensaje_error": item.mensaje_error
        }

    async def enrich_item_by_id(self, item_id: int, db: Session, classify_with_ai: bool = True) -> Optional[Dict[str, Any]]:
        """
        Enriquece un ítem individual buscando por su ID de tabla.
        """
        item = db.query(DSpaceEnrichmentQueue).filter(DSpaceEnrichmentQueue.id == item_id).first()
        if not item:
            return None
        return await self.enrich_item(item, db, classify_with_ai=classify_with_ai)

    async def enrich_item_by_uuid(self, dspace_uuid: str, db: Session, classify_with_ai: bool = True) -> Optional[Dict[str, Any]]:
        """
        Enriquece un ítem individual buscando por su UUID de DSpace.
        """
        item = db.query(DSpaceEnrichmentQueue).filter(DSpaceEnrichmentQueue.dspace_uuid == dspace_uuid).first()
        if not item:
            return None
        return await self.enrich_item(item, db, classify_with_ai=classify_with_ai)

    async def enrich_batch(self, limit: int = 5, estado_filtro: str = "PENDIENTE", classify_with_ai: bool = True, db: Session = None) -> Dict[str, Any]:
        """
        Toma un lote de registros pendientes en la cola y los procesa secuencialmente
        para respetar las políticas de tasa (rate limits) de las fuentes externas.
        """
        items = (
            db.query(DSpaceEnrichmentQueue)
            .filter(DSpaceEnrichmentQueue.estado == estado_filtro)
            .order_by(DSpaceEnrichmentQueue.id.asc())
            .limit(limit)
            .all()
        )

        resultados = []
        for it in items:
            res = await self.enrich_item(it, db, classify_with_ai=classify_with_ai)
            resultados.append(res)
            # Pequeña pausa de cortesía entre llamadas
            await asyncio.sleep(0.5)

        completos = sum(1 for r in resultados if r.get("estado") == "COMPLETO")
        enriquecidos_fuentes = sum(1 for r in resultados if r.get("estado") == "ENRIQUECIDO_FUENTES")
        clasificados_llm = sum(1 for r in resultados if r.get("estado") == "CLASIFICADO_LLM")
        no_encontrados = sum(1 for r in resultados if r.get("estado") == "NO_ENCONTRADO")
        errores = sum(1 for r in resultados if r.get("estado") == "ERROR")

        return {
            "total_procesados": len(resultados),
            "resumen": {
                "completos": completos,
                "enriquecidos_fuentes": enriquecidos_fuentes,
                "clasificados_llm": clasificados_llm,
                "no_encontrados": no_encontrados,
                "errores": errores
            },
            "items": resultados
        }

    async def generate_vriic_sample(
        self,
        db: Session,
        sample_size: int = 35,
        output_filename: str = "muestra_clasificaciones_vriic.xlsx",
        force_reclassify: bool = False
    ) -> Dict[str, Any]:
        """
        Extrae una muestra de publicaciones desde 'dspace_enrichment_queue' que tengan título y resumen original,
        las clasifica en áreas OCDE y ODS usando el LLM (Ollama / LLaMA 3.2),
        persiste las clasificaciones en la base de datos (con su uuid, título y resumen)
        y exporta la muestra formateada en un archivo Excel en la raíz del proyecto para validación con la VRIIC.
        Si force_reclassify=True, ignora clasificaciones previas y vuelve a clasificarlas desde cero con el LLM.
        """
        
        # 1. Extraer publicaciones que tengan título y resumen original válido
        tiene_clasificacion = and_(
            DSpaceEnrichmentQueue.area_ocde.isnot(None),
            DSpaceEnrichmentQueue.area_ods.isnot(None)
        )
        order_criteria = (
            [DSpaceEnrichmentQueue.id.asc()]
            if force_reclassify
            else [
                case((tiene_clasificacion, 0), else_=1),
                case((tiene_clasificacion, DSpaceEnrichmentQueue.updated_at), else_=None).desc().nullslast(),
                DSpaceEnrichmentQueue.id.asc(),
            ]
        )

        candidatos = (
            db.query(DSpaceEnrichmentQueue)
            .filter(
                DSpaceEnrichmentQueue.titulo.isnot(None),
                func.length(DSpaceEnrichmentQueue.titulo) > 5,
                DSpaceEnrichmentQueue.resumen_original.isnot(None),
                func.length(DSpaceEnrichmentQueue.resumen_original) > 20,
                ~DSpaceEnrichmentQueue.resumen_original.in_(["No disponible", "Sin resumen", "[No abstract available]"])
            )
            # Si forzamos reclasificación, ordenamos por ID; si no, priorizamos las clasificadas más recientes
            .order_by(*order_criteria)
            .limit(sample_size)
            .all()
        )

        if not candidatos:
            raise Exception("No se encontraron publicaciones con título y resumen original en la tabla dspace_enrichment_queue.")

        # 2. Clasificar los que aún no tengan clasificación OCDE u ODS (o todos si force_reclassify=True)
        clasificados_nuevos = 0
        ya_clasificados = 0

        for item in candidatos:
            necesita_clasificar_ocde = force_reclassify or not item.area_ocde
            necesita_clasificar_ods = force_reclassify or not item.area_ods

            if necesita_clasificar_ocde or necesita_clasificar_ods:
                abstract_para_llm = item.abstract_enriquecido or item.resumen_original
                keywords_str = ", ".join(item.palabras_clave) if isinstance(item.palabras_clave, list) else (str(item.palabras_clave) if item.palabras_clave else None)

                item_uuid = uuid.uuid4()
                if item.dspace_uuid:
                    try:
                        item_uuid = uuid.UUID(str(item.dspace_uuid))
                    except (ValueError, TypeError):
                        pass

                try:
                    res_ms2 = await self.ms2_client.classify(
                        item_id=item_uuid,
                        title=item.titulo,
                        abstract=abstract_para_llm,
                        keywords=keywords_str
                    )
                    if necesita_clasificar_ocde:
                        if res_ms2.get("ocde_categories"):
                            item.area_ocde = res_ms2["ocde_categories"]
                        elif res_ms2.get("area_ocde"):
                            item.area_ocde = res_ms2["area_ocde"] if isinstance(res_ms2["area_ocde"], list) else [res_ms2["area_ocde"]]
                    if necesita_clasificar_ods:
                        if res_ms2.get("ods_categories"):
                            item.area_ods = res_ms2["ods_categories"]
                        elif res_ms2.get("area_ods"):
                            item.area_ods = res_ms2["area_ods"] if isinstance(res_ms2["area_ods"], list) else [res_ms2["area_ods"]]
                except Exception as e_ms2:
                    print(f"Error clasificando en MS2 para {item.dspace_uuid or item.id}: {e_ms2}")

                if item.area_ocde and item.area_ods:
                    item.estado = "COMPLETO"
                elif item.area_ocde or item.area_ods:
                    item.estado = "CLASIFICADO_LLM"

                item.updated_at = datetime.utcnow()
                db.commit()
                db.refresh(item)
                clasificados_nuevos += 1
                await asyncio.sleep(0.1)
            else:
                ya_clasificados += 1

        # 3. Generar el archivo Excel
        try:
            import openpyxl
            from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
            from openpyxl.utils import get_column_letter
        except ImportError:
            raise RuntimeError("openpyxl no está instalado en el entorno. Instálalo con `pip install openpyxl` para exportar a Excel.")

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Muestra VRIIC"
        ws.views.sheetView[0].showGridLines = True

        # Estilos visuales institucionales
        fuente_titulo = Font(name="Calibri", size=14, bold=True, color="002060")
        fuente_subtitulo = Font(name="Calibri", size=10, italic=True, color="595959")
        fuente_header = Font(name="Calibri", size=10, bold=True, color="FFFFFF")
        fuente_datos = Font(name="Calibri", size=9)
        
        fill_header = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid")
        fill_header_vriic = PatternFill(start_color="2F5597", end_color="2F5597", fill_type="solid")
        fill_par = PatternFill(start_color="F2F5F9", end_color="F2F5F9", fill_type="solid")
        fill_impar = PatternFill(start_color="FFFFFF", end_color="FFFFFF", fill_type="solid")
        
        borde_fino = Border(
            left=Side(style="thin", color="D9D9D9"),
            right=Side(style="thin", color="D9D9D9"),
            top=Side(style="thin", color="D9D9D9"),
            bottom=Side(style="thin", color="D9D9D9")
        )

        align_center = Alignment(horizontal="center", vertical="top", wrap_text=True)
        align_left = Alignment(horizontal="left", vertical="top", wrap_text=True)

        # Encabezado institucional
        ws.merge_cells("A1:N1")
        ws["A1"] = "MUESTRA DE CLASIFICACIÓN DE PUBLICACIONES (ÁREAS OCDE Y ODS) - VALIDACIÓN VRIIC"
        ws["A1"].font = fuente_titulo
        ws["A1"].alignment = Alignment(horizontal="left", vertical="center")

        ws.merge_cells("A2:N2")
        ws["A2"] = f"Generado: {datetime.now().strftime('%Y-%m-%d %H:%M')} | Modelo: LLaMA 3.2 (Ollama) | Total Muestra: {len(candidatos)} publicaciones | Fuente: Base de datos dspace_enrichment_queue"
        ws["A2"].font = fuente_subtitulo
        ws["A2"].alignment = Alignment(horizontal="left", vertical="center")

        headers = [
            "N°",
            "UUID DSpace",
            "DOI",
            "Título de la Publicación",
            "Resumen (Abstract Original)",
            "Código Disciplina OCDE",
            "Área / Disciplina OCDE",
            "Justificación OCDE (Modelo)",
            "Código ODS",
            "Nombre ODS",
            "Justificación ODS (Modelo)",
            "Validación VRIIC - OCDE",
            "Validación VRIIC - ODS",
            "Observaciones VRIIC"
        ]

        ws.append([]) # Fila 3 en blanco
        ws.append(headers) # Fila 4
        
        header_row_idx = 4
        for col_idx, col_name in enumerate(headers, 1):
            cell = ws.cell(row=header_row_idx, column=col_idx)
            cell.font = fuente_header
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            if "VRIIC" in col_name:
                cell.fill = fill_header_vriic
            else:
                cell.fill = fill_header
            cell.border = borde_fino
        
        ws.row_dimensions[header_row_idx].height = 28

        # Llenar datos de cada publicación
        for idx, item in enumerate(candidatos, 1):
            # Parsear OCDE de manera defensiva (soporta lista de dicts, lista de strings, dict único o string)
            cods, noms, justs = [], [], []
            raw_ocde = item.area_ocde
            if isinstance(raw_ocde, str):
                try:
                    import json
                    parsed = json.loads(raw_ocde)
                    if isinstance(parsed, (list, dict)):
                        raw_ocde = parsed
                except Exception:
                    pass
            if isinstance(raw_ocde, dict):
                raw_ocde = [raw_ocde]
            elif raw_ocde and not isinstance(raw_ocde, list):
                raw_ocde = [str(raw_ocde)]

            if raw_ocde and isinstance(raw_ocde, list):
                for c in raw_ocde:
                    if isinstance(c, dict):
                        cod = str(c.get("codigo_disciplina") or c.get("codigo_area") or "").strip()
                        nom = str(c.get("nombre_disciplina") or c.get("nombre_area") or "").strip()
                        just = str(c.get("justificacion") or "").strip()
                    elif isinstance(c, str):
                        c_str = c.strip()
                        if " - " in c_str:
                            parts = c_str.split(" - ", 1)
                            cod = parts[0].strip()
                            nom = parts[1].strip()
                        else:
                            cod = ""
                            nom = c_str
                        just = ""
                    else:
                        cod, nom, just = "", str(c), ""

                    if cod: cods.append(cod)
                    if nom: noms.append(nom)
                    if just: justs.append(just)

            cod_ocde_str = "\n".join(cods)
            nom_ocde_str = "\n".join(noms)
            just_ocde_str = "\n---\n".join([j for j in justs if j])

            # Parsear ODS de manera defensiva (soporta lista de dicts, lista de strings, dict único o string)
            nums, noms_ods, justs_ods = [], [], []
            raw_ods = item.area_ods
            if isinstance(raw_ods, str):
                try:
                    import json
                    parsed = json.loads(raw_ods)
                    if isinstance(parsed, (list, dict)):
                        raw_ods = parsed
                except Exception:
                    pass
            if isinstance(raw_ods, dict):
                raw_ods = [raw_ods]
            elif raw_ods and not isinstance(raw_ods, list):
                raw_ods = [str(raw_ods)]

            if raw_ods and isinstance(raw_ods, list):
                for o in raw_ods:
                    if isinstance(o, dict):
                        num = str(o.get("numero_ods") or "").strip()
                        nom = str(o.get("nombre_ods") or "").strip()
                        just = str(o.get("justificacion") or "").strip()
                        if num and not num.upper().startswith("ODS"):
                            num = f"ODS {num}"
                    elif isinstance(o, str):
                        o_str = o.strip()
                        if ":" in o_str:
                            parts = o_str.split(":", 1)
                            num = parts[0].strip()
                            nom = parts[1].strip()
                        elif " - " in o_str:
                            parts = o_str.split(" - ", 1)
                            num = parts[0].strip()
                            nom = parts[1].strip()
                        else:
                            num = ""
                            nom = o_str
                        just = ""
                    else:
                        num, nom, just = "", str(o), ""

                    if num: nums.append(num)
                    if nom: noms_ods.append(nom)
                    if just: justs_ods.append(just)

            num_ods_str = "\n".join(nums)
            nom_ods_str = "\n".join(noms_ods)
            just_ods_str = "\n---\n".join([j for j in justs_ods if j])

            row_data = [
                idx,
                item.dspace_uuid,
                item.doi or "No registrado",
                item.titulo or "",
                item.resumen_original or "",
                cod_ocde_str,
                nom_ocde_str,
                just_ocde_str,
                num_ods_str,
                nom_ods_str,
                just_ods_str,
                "", # Celda para VRIIC - OCDE
                "", # Celda para VRIIC - ODS
                ""  # Observaciones VRIIC
            ]

            ws.append(row_data)
            current_row = ws.max_row
            fill_actual = fill_par if idx % 2 == 0 else fill_impar

            for c_idx in range(1, len(row_data) + 1):
                cell = ws.cell(row=current_row, column=c_idx)
                cell.font = fuente_datos
                cell.fill = fill_actual
                cell.border = borde_fino
                if c_idx in [1, 2, 3, 6, 9]:
                    cell.alignment = align_center
                else:
                    cell.alignment = align_left

        # Configurar anchos de columna óptimos
        col_widths = {
            1: 6,    # N°
            2: 38,   # UUID
            3: 24,   # DOI
            4: 40,   # Título
            5: 65,   # Resumen
            6: 18,   # Código OCDE
            7: 30,   # Disciplina OCDE
            8: 45,   # Justificación OCDE
            9: 14,   # N° ODS
            10: 28,  # Nombre ODS
            11: 45,  # Justificación ODS
            12: 24,  # Validación OCDE
            13: 24,  # Validación ODS
            14: 30   # Observaciones
        }

        for col_idx, width in col_widths.items():
            ws.column_dimensions[get_column_letter(col_idx)].width = width

        # Verificar si ya existe una planilla idéntica en la ruta destino; si existe, eliminarla antes de recrearla
        file_path = os.path.abspath(output_filename)
        archivo_previo_eliminado = False
        if os.path.exists(file_path):
            if os.path.isfile(file_path):
                os.remove(file_path)
                archivo_previo_eliminado = True
            else:
                raise IsADirectoryError(
                    f"La ruta destino '{file_path}' corresponde a un directorio y no a un archivo."
                )

        parent_dir = os.path.dirname(file_path)
        if parent_dir:
            os.makedirs(parent_dir, exist_ok=True)

        wb.save(file_path)

        return {
            "status": "success",
            "archivo_generado": output_filename,
            "ruta_absoluta": file_path,
            "archivo_previo_eliminado": archivo_previo_eliminado,
            "total_muestra": len(candidatos),
            "clasificados_nuevos": clasificados_nuevos,
            "ya_clasificados_reutilizados": ya_clasificados,
            "mensaje": (
                f"Planilla previa eliminada y muestra de {len(candidatos)} publicaciones regenerada exitosamente en {output_filename}"
                if archivo_previo_eliminado
                else f"Muestra de {len(candidatos)} publicaciones generada y guardada exitosamente en {output_filename}"
            )
        }

    def reset_classifications(
        self,
        db: Session,
        item_id: Optional[int] = None,
        dspace_uuid: Optional[str] = None,
        reset_all: bool = False
    ) -> Dict[str, Any]:
        """
        Elimina las clasificaciones (area_ocde y area_ods) de los registros en dspace_enrichment_queue
        para permitir volver a clasificarlos desde cero.
        - Si se especifica item_id o dspace_uuid: resetea ese ítem en particular.
        - Si reset_all=True: resetea todos los registros que tengan áreas OCDE u ODS asignadas.
        """
        query = db.query(DSpaceEnrichmentQueue)
        if item_id:
            query = query.filter(DSpaceEnrichmentQueue.id == item_id)
        elif dspace_uuid:
            query = query.filter(DSpaceEnrichmentQueue.dspace_uuid == dspace_uuid)
        elif reset_all:
            query = query.filter(
                (DSpaceEnrichmentQueue.area_ocde.isnot(None)) | 
                (DSpaceEnrichmentQueue.area_ods.isnot(None))
            )
        else:
            return {
                "status": "error",
                "mensaje": "Debe especificar 'item_id', 'dspace_uuid' o indicar 'reset_all=True' para reiniciar las clasificaciones."
            }

        items = query.all()
        if not items:
            return {
                "status": "info",
                "total_reseteados": 0,
                "mensaje": "No se encontraron registros con clasificaciones para reiniciar."
            }

        for item in items:
            item.area_ocde = None
            item.area_ods = None
            if item.abstract_enriquecido:
                item.estado = "ENRIQUECIDO_FUENTES"
            else:
                item.estado = "PENDIENTE"
            item.updated_at = datetime.utcnow()

        db.commit()

        return {
            "status": "success",
            "total_reseteados": len(items),
            "mensaje": f"Se eliminaron las clasificaciones de {len(items)} publicación(es) y se restableció su estado."
        }
