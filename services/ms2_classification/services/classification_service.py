import json
import os
import re
import time
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

try:
    from models import LLMClassificationLog, Category, OCDEItemDTO, ODSItemDTO, ClassificationResultResponse
    from services.ollama_client import generate_text, OllamaRequest
    from services.ocde_service import (
        get_ocde_subareas_formatted,
        get_ocde_disciplines_formatted,
        get_ocde_discipline_by_code
    )
    from services.ods_service import get_ods_areas_formatted
except ImportError:
    from services.ms2_classification.models import LLMClassificationLog, Category, OCDEItemDTO, ODSItemDTO, ClassificationResultResponse
    from services.ms2_classification.services.ollama_client import generate_text, OllamaRequest
    from services.ms2_classification.services.ocde_service import (
        get_ocde_subareas_formatted,
        get_ocde_disciplines_formatted,
        get_ocde_discipline_by_code
    )
    from services.ms2_classification.services.ods_service import get_ods_areas_formatted

MODEL_VERSION = os.getenv("OLLAMA_MODEL", "llama3.2")
PROMPT_VERSION = "v3.0-hierarchical"


# =============================================================================
# ESQUEMAS PYDANTIC PARA CLASIFICACIÓN JERÁRQUICA (STRUCTURED OUTPUTS)
# =============================================================================

class SubareaPick(BaseModel):
    codigo_subarea: str = Field(description="Código exacto de la subárea en formato X.XX.00")
    justificacion: str = Field(description="Por qué corresponde a esta subárea")


class Step1Response(BaseModel):
    is_info_sufficient: bool = Field(default=True, description="Indica si la información es suficiente para clasificar")
    razonamiento: str = Field(default="", description="Breve análisis de 1-2 oraciones sobre el tema y método del artículo")
    subareas: List[SubareaPick] = Field(default_factory=list, max_length=2)


class DisciplinaPick(BaseModel):
    codigo_disciplina: str = Field(description="Código exacto de la disciplina en formato X.XX.XX")
    prioridad: int = Field(default=1, ge=1, le=2, description="1 para disciplina principal, 2 para secundaria")
    justificacion: str = Field(default="", description="Justificación de la elección")
    confidence_score: float = Field(default=0.95, ge=0.0, le=1.0, description="Nivel de confianza entre 0.0 y 1.0")


class Step2Response(BaseModel):
    is_info_sufficient: bool = Field(default=True, description="Indica si la información es suficiente")
    razonamiento: str = Field(default="", description="Razonamiento de la selección de disciplinas")
    clasificaciones: List[DisciplinaPick] = Field(default_factory=list, max_length=2)


# =============================================================================
# PROMPTS JERÁRQUICOS EN 2 PASOS (OPTIMIZADOS PARA LLAMA 3.2 3B)
# =============================================================================

PROMPT_STEP_1_SUBAREA = """Eres un bibliotecario científico experto en la taxonomía FORD de la OCDE.
Analiza los metadatos del artículo e identifica las 1 o 2 SUBÁREAS OCDE más pertinentes.
Ten en cuenta que el catálogo oficial está en inglés, por lo que debes asociar el contenido en español o inglés al concepto correspondiente.

ARTÍCULO:
- Título: {title}
- Resumen: {abstract}
- Palabras clave: {keywords}

CATÁLOGO DE SUBÁREAS PERMITIDAS (42 opciones):
{subareas_list}

INSTRUCCIONES:
1. Evalúa el problema científico central y la metodología principal del artículo.
2. Si el título y el resumen son vacíos, demasiado cortos (< 20 palabras) o ambiguos para determinar una disciplina científica, marca "is_info_sufficient": false y deja "subareas" vacío.
3. Selecciona mínimo 1 y máximo 2 códigos de la lista permitida (formato "X.XX.00"). No inventes códigos.
4. Responde EXCLUSIVAMENTE con un objeto JSON válido siguiendo este esquema:

{{
  "is_info_sufficient": true,
  "razonamiento": "Breve análisis de 1-2 oraciones sobre el tema y método del artículo.",
  "subareas": [
    {{
      "codigo_subarea": "1.02.00",
      "justificacion": "Por qué corresponde a esta subárea."
    }}
  ]
}}"""

PROMPT_STEP_2_DISCIPLINA = """Eres un bibliotecario científico experto en la taxonomía FORD de la OCDE.
Dado el siguiente artículo y las subáreas preseleccionadas, elige ÚNICAMENTE 1 o 2 DISCIPLINAS específicas de la lista filtrada.
Ten en cuenta que el catálogo oficial está en inglés, por lo que debes asociar el contenido en español o inglés al concepto correspondiente.

ARTÍCULO:
- Título: {title}
- Resumen: {abstract}
- Palabras clave: {keywords}

DISCIPLINAS PERMITIDAS (ordenadas por Área > Subárea > Disciplina):
{filtered_disciplines_list}

REGLAS ESTRICTAS:
1. Selecciona solo códigos exactos de la lista anterior (formato "X.XX.XX").
2. Prioridad 1: Disciplina principal del objeto de estudio. Prioridad 2 (opcional): Disciplina secundaria solo si el artículo es genuinamente interdisciplinario.
3. Regla de desempate: Si se aplica una técnica (ej. Machine Learning o Estadística) a un problema específico (ej. Oncología o Agronomía), asigna Prioridad 1 al dominio del problema y Prioridad 2 a la técnica.
4. No incluyas texto fuera del JSON.

EJEMPLO DE SALIDA ESPERADA:
{{
  "is_info_sufficient": true,
  "razonamiento": "El estudio desarrolla algoritmos de aprendizaje profundo para segmentar imágenes de retina.",
  "clasificaciones": [
    {{
      "codigo_disciplina": "3.02.08",
      "prioridad": 1,
      "justificacion": "El objetivo clínico principal es el diagnóstico en oftalmología.",
      "confidence_score": 0.92
    }},
    {{
      "codigo_disciplina": "1.02.01",
      "prioridad": 2,
      "justificacion": "Utiliza redes neuronales convolucionales como metodología central.",
      "confidence_score": 0.85
    }}
  ]
}}"""


class MS2ClassificationWorker:
    """
    Microservicio 2: Inferencia semántica con LLM local (Ollama).
    Implementa clasificación jerárquica en 2 pasos para taxonomía FORD OCDE.
    Escribe exclusivamente en LLM_Classification_Log y gestiona Category.
    """

    async def execute_classification(
        self,
        item_id: uuid.UUID,
        title: Optional[str],
        abstract: Optional[str],
        keywords: Optional[str],
        db: Session,
        temperature: float = 0.0,
        repetition_number: int = 1
    ) -> ClassificationResultResponse:
        start_total = time.time()

        ocde_items, ocde_suff, ocde_reason, ocde_ms = await self._classify_ocde(
            item_id=item_id,
            title=title,
            abstract=abstract,
            keywords=keywords,
            db=db,
            temperature=temperature,
            repetition_number=repetition_number
        )

        ods_items, ods_suff, ods_reason, ods_ms = await self._classify_ods(
            item_id=item_id,
            title=title,
            abstract=abstract,
            keywords=keywords,
            db=db,
            temperature=temperature,
            repetition_number=repetition_number
        )

        total_ms = int((time.time() - start_total) * 1000)
        overall_suff = ocde_suff and ods_suff

        return ClassificationResultResponse(
            is_info_sufficient=overall_suff,
            ocde_categories=ocde_items,
            ods_categories=ods_items,
            ocde_reasoning=ocde_reason,
            ods_reasoning=ods_reason,
            execution_time_total_ms=total_ms,
            area_ocde=[f"{c.codigo_disciplina} - {c.nombre_disciplina} ({c.nombre_area})" for c in ocde_items] if ocde_items else None,
            area_ods=[f"ODS {o.numero_ods}: {o.nombre_ods}" for o in ods_items] if ods_items else None
        )

    async def _classify_ocde(
        self,
        item_id: uuid.UUID,
        title: Optional[str],
        abstract: Optional[str],
        keywords: Optional[str],
        db: Session,
        temperature: float,
        repetition_number: int
    ) -> Tuple[List[OCDEItemDTO], bool, str, int]:
        """
        Clasificación Jerárquica en 2 Pasos (Recomendada para Llama 3.2 3B):
        - Paso 1: Selección de 1 o 2 subáreas entre las 42 permitidas.
        - Paso 2: Filtrado y selección de 1 o 2 disciplinas hijas (~3 a 16 opciones).
        - Validación determinista contra Areas_OCDE.xlsx para evitar alucinaciones.
        """
        t0 = time.time()
        title_str = title or "No disponible"
        abstract_str = abstract or "No disponible"
        keywords_str = keywords or "No disponible"

        has_content = bool(
            (abstract and len(abstract.strip().split()) >= 15) or
            (title and len(title.strip().split()) >= 4)
        )
        if not has_content:
            reason = "Información insuficiente: título y resumen ausentes o con menos de 20 palabras."
            elapsed = int((time.time() - t0) * 1000)
            self._save_log(
                db=db,
                item_id=item_id,
                cls_type="OCDE",
                prompt="Validación de entrada: texto insuficiente",
                temperature=temperature,
                rep=repetition_number,
                result_json={"is_info_sufficient": False, "subareas": [], "clasificaciones": []},
                reason=reason,
                is_suff=False,
                elapsed=elapsed
            )
            return [], False, reason, elapsed

        # ----------------------------------------------------
        # PASO 1: Detectar Subáreas (42 opciones)
        # ----------------------------------------------------
        subareas_text = get_ocde_subareas_formatted()
        p1 = PROMPT_STEP_1_SUBAREA.format(
            title=title_str,
            abstract=abstract_str,
            keywords=keywords_str,
            subareas_list=subareas_text
        )

        step1_res = {}
        step2_res = {}
        items: List[OCDEItemDTO] = []
        is_suff = True
        reason = ""

        try:
            req1 = OllamaRequest(
                model=MODEL_VERSION,
                prompt=p1,
                format=Step1Response.model_json_schema(),
                options={
                    "temperature": temperature,
                    "num_ctx": 4096,
                    "seed": 42
                }
            )
            res1 = await generate_text(req1)
            raw1 = res1.response.strip()
            m1 = re.search(r'(\{.*\})', raw1, re.DOTALL)
            if m1:
                raw1 = m1.group(1)
            step1_data = Step1Response.model_validate_json(raw1)
            step1_res = step1_data.model_dump()

            if not step1_data.is_info_sufficient or not step1_data.subareas:
                reason = step1_data.razonamiento or "Información insuficiente para determinar subáreas OCDE."
                elapsed = int((time.time() - t0) * 1000)
                self._save_log(
                    db=db,
                    item_id=item_id,
                    cls_type="OCDE",
                    prompt=p1,
                    temperature=temperature,
                    rep=repetition_number,
                    result_json={"step1": step1_res, "step2": None},
                    reason=reason,
                    is_suff=False,
                    elapsed=elapsed
                )
                return [], False, reason, elapsed

            codigos_sub = [s.codigo_subarea.strip() for s in step1_data.subareas if s.codigo_subarea]

            # ----------------------------------------------------
            # PASO 2: Detectar Disciplinas Específicas (~3 a 16 opciones)
            # ----------------------------------------------------
            disc_text = get_ocde_disciplines_formatted(codigos_sub)
            if not disc_text:
                disc_text = get_ocde_disciplines_formatted()

            p2 = PROMPT_STEP_2_DISCIPLINA.format(
                title=title_str,
                abstract=abstract_str,
                keywords=keywords_str,
                filtered_disciplines_list=disc_text
            )

            req2 = OllamaRequest(
                model=MODEL_VERSION,
                prompt=p2,
                format=Step2Response.model_json_schema(),
                options={
                    "temperature": temperature,
                    "num_ctx": 4096,
                    "seed": 42
                }
            )
            res2 = await generate_text(req2)
            raw2 = res2.response.strip()
            m2 = re.search(r'(\{.*\})', raw2, re.DOTALL)
            if m2:
                raw2 = m2.group(1)
            step2_data = Step2Response.model_validate_json(raw2)
            step2_res = step2_data.model_dump()

            reason = f"Paso 1 (Subáreas): {step1_data.razonamiento}. Paso 2 (Disciplinas): {step2_data.razonamiento}".strip()

            # Enriquecer determinísticamente desde Areas_OCDE.xlsx (evita alucinación de nombres)
            for it in step2_data.clasificaciones:
                row_excel = get_ocde_discipline_by_code(it.codigo_disciplina)
                if row_excel:
                    items.append(OCDEItemDTO(
                        codigo_area=row_excel["id_area"],
                        nombre_area=row_excel["nombre_area"],
                        codigo_subarea=row_excel["id_subarea"],
                        nombre_subarea=row_excel["nombre_subarea"],
                        codigo_disciplina=row_excel["id_disciplina"],
                        nombre_disciplina=row_excel["nombre_disciplina"],
                        justificacion=it.justificacion,
                        confidence_score=float(it.confidence_score)
                    ))

            # Ordenar por prioridad asignada
            is_suff = step2_data.is_info_sufficient and len(items) > 0

        except Exception as e:
            reason = f"Error en inferencia jerárquica OCDE: {e}"
            step1_res = {"error": str(e)}
            is_suff = False

        elapsed = int((time.time() - t0) * 1000)

        # Bitácora inmutable en LLMClassificationLog
        self._save_log(
            db=db,
            item_id=item_id,
            cls_type="OCDE",
            prompt=p2 if "p2" in locals() else p1,
            temperature=temperature,
            rep=repetition_number,
            result_json={
                "step1": step1_res,
                "step2": step2_res,
                "clasificaciones_finales": [i.model_dump() for i in items]
            },
            reason=reason,
            is_suff=is_suff,
            elapsed=elapsed
        )

        return items, is_suff, reason, elapsed

    async def _classify_ods(
        self,
        item_id: uuid.UUID,
        title: Optional[str],
        abstract: Optional[str],
        keywords: Optional[str],
        db: Session,
        temperature: float,
        repetition_number: int
    ) -> Tuple[List[ODSItemDTO], bool, str, int]:
        t0 = time.time()
        areas_text = get_ods_areas_formatted()
        is_suff = bool(abstract and len(abstract.strip()) >= 50)

        prompt = f"""Eres un experto en los 17 ODS de la ONU (2015). Clasifica el impacto socioeconómico de este artículo en máximo 2 ODS:
TÍTULO: {title or 'No disponible'}
RESUMEN: {abstract or 'No disponible'}
PALABRAS CLAVE: {keywords or 'No disponible'}

LISTA ODS:
{areas_text}

REGLAS:
1. Máximo 2 ODS.
2. Si la información es insuficiente, is_info_sufficient: false.
3. Responde SOLO un JSON:
{{
  "is_info_sufficient": true,
  "razonamiento": "explicación",
  "clasificaciones": [
    {{
      "numero_ods": "3",
      "nombre_ods": "Salud y Bienestar",
      "justificacion": "explicación",
      "confidence_score": 0.95
    }}
  ]
}}
"""
        items = []
        reason = ""
        res_json = {}

        try:
            res = await generate_text(OllamaRequest(
                model=MODEL_VERSION,
                prompt=prompt,
                options={
                    "temperature": temperature,
                    "num_ctx": 4096,
                    "seed": 42
                }
            ))
            raw = res.response.strip()
            m = re.search(r'(\{.*\})', raw, re.DOTALL)
            if m:
                raw = m.group(1)
            res_json = json.loads(raw)

            is_suff = res_json.get("is_info_sufficient", is_suff)
            reason = res_json.get("razonamiento", "")
            for it in res_json.get("clasificaciones", [])[:2]:
                items.append(ODSItemDTO(
                    numero_ods=str(it.get("numero_ods", "")),
                    nombre_ods=str(it.get("nombre_ods", "")),
                    justificacion=str(it.get("justificacion", "")),
                    confidence_score=float(it.get("confidence_score", 0.95))
                ))
        except Exception as e:
            reason = f"Error en inferencia ODS: {e}"
            res_json = {"error": str(e)}

        elapsed = int((time.time() - t0) * 1000)

        self._save_log(
            db=db,
            item_id=item_id,
            cls_type="ODS",
            prompt=prompt,
            temperature=temperature,
            rep=repetition_number,
            result_json=res_json,
            reason=reason,
            is_suff=is_suff,
            elapsed=elapsed
        )

        return items, is_suff, reason, elapsed

    def _save_log(
        self,
        db: Session,
        item_id: uuid.UUID,
        cls_type: str,
        prompt: str,
        temperature: float,
        rep: int,
        result_json: Any,
        reason: str,
        is_suff: bool,
        elapsed: int
    ):
        if not db or not item_id:
            return
        log = LLMClassificationLog(
            id_item_enrichment=item_id,
            classification_type=cls_type,
            model_version=MODEL_VERSION,
            prompt_template_version=PROMPT_VERSION,
            prompt=prompt[:2000],
            temperature=temperature,
            repetition_number=rep,
            result_json=result_json,
            llm_reasoning=reason,
            is_info_sufficient=is_suff,
            execution_time_ms=elapsed,
            created_at=datetime.utcnow()
        )
        db.add(log)
        db.commit()
