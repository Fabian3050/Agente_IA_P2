import os
import json
import re
import time
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.orm import Session

from app.services.metadata_service import MetadataService
from app.clients.ollama_client import generate_text
from app.models.ollama_model import OllamaGenerateRequest
from app.services.ocde_service import (
    get_ocde_areas_formatted,
    get_ocde_subareas_formatted,
    get_ocde_disciplines_formatted,
    get_ocde_discipline_by_code
)
from app.services.ods_service import get_ods_areas_formatted
from pydantic import BaseModel, Field
from app.models.classification_model import (
    OCDEClassificationResponse, 
    ODSClassificationResponse,
    OCDEClassificationItem,
    ODSClassificationItem,
    OCDEClassificationResult,
    ODSClassificationResult
)
from app.models.metadata_model import MetadataResponse
from app.models.db_models import (
    LLMClassificationLog, Category, ItemCategory
)

MODEL_EXACT_VERSION = os.getenv("OLLAMA_MODEL", "llama3.2")
PROMPT_VERSION = "v3.0-hierarchical"
PRODUCTION_TEMPERATURE = 0.0

class SubareaPick(BaseModel):
    codigo_subarea: str = Field(description="Código de la subárea en formato X.XX.00")
    justificacion: str = Field(description="Por qué corresponde a esta subárea")

class Step1Response(BaseModel):
    is_info_sufficient: bool = Field(default=True, description="Indica si la información es suficiente")
    razonamiento: str = Field(default="", description="Breve análisis de 1-2 oraciones")
    subareas: List[SubareaPick] = Field(default_factory=list, max_length=2)

class DisciplinaPick(BaseModel):
    codigo_disciplina: str = Field(description="Código exacto de la disciplina en formato X.XX.XX")
    prioridad: int = Field(default=1, ge=1, le=2)
    justificacion: str = Field(default="")
    confidence_score: float = Field(default=0.95, ge=0.0, le=1.0)

class Step2Response(BaseModel):
    is_info_sufficient: bool = Field(default=True)
    razonamiento: str = Field(default="")
    clasificaciones: List[DisciplinaPick] = Field(default_factory=list, max_length=2)

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


class ClassificationService:
    """
    Microservicio 2: Clasificación Área OCDE / ODS (MS2).
    Inferencia semántica local con LLM Llama 3.2 (3B) en Ollama.
    Escribe exclusivamente en LLM_Classification_Log y Category.
    """

    def __init__(self):
        self.metadata_service = MetadataService()

    async def classify_item_for_enrichment(
        self,
        item_id: Any,
        title: Optional[str],
        abstract: Optional[str],
        keywords: Optional[str],
        db: Session,
        temperature: float = PRODUCTION_TEMPERATURE,
        repetition_number: int = 1
    ) -> Dict[str, Any]:
        """
        Ejecuta la clasificación combinada OCDE y ODS para un ItemEnrichment,
        registrando la bitácora inmutable en LLMClassificationLog (MS2).
        """
        ocde_res, ocde_log = await self.classify_ocde_with_logging(
            item_id=item_id,
            title=title,
            abstract=abstract,
            db=db,
            temperature=temperature,
            repetition_number=repetition_number,
            keywords=keywords
        )

        ods_res, ods_log = await self.classify_ods_with_logging(
            item_id=item_id,
            title=title,
            abstract=abstract,
            keywords=keywords,
            db=db,
            temperature=temperature,
            repetition_number=repetition_number
        )

        return {
            "ocde": ocde_res,
            "ods": ods_res,
            "ocde_log_id": ocde_log.id if ocde_log else None,
            "ods_log_id": ods_log.id if ods_log else None
        }

    async def classify_ocde_with_logging(
        self,
        item_id: Any,
        title: Optional[str],
        abstract: Optional[str],
        db: Session,
        temperature: float = PRODUCTION_TEMPERATURE,
        repetition_number: int = 1,
        keywords: Optional[str] = None
    ) -> Tuple[OCDEClassificationResponse, Optional[LLMClassificationLog]]:
        """Inferencia jerárquica OCDE en 2 pasos con registro auditable en LLMClassificationLog."""
        start_time = time.time()
        title_str = title or "No disponible"
        abstract_str = abstract or "No disponible"
        keywords_str = keywords or "No disponible"

        has_content = bool(
            (abstract and len(abstract.strip().split()) >= 15) or
            (title and len(title.strip().split()) >= 4)
        )
        if not has_content:
            elapsed_ms = int((time.time() - start_time) * 1000)
            log_entry = None
            if item_id and db:
                log_entry = LLMClassificationLog(
                    id_item_enrichment=item_id,
                    classification_type="OCDE",
                    model_version=MODEL_EXACT_VERSION,
                    prompt_template_version=PROMPT_VERSION,
                    prompt="Validación de entrada: texto insuficiente",
                    temperature=temperature,
                    repetition_number=repetition_number,
                    result_json={"is_info_sufficient": False, "subareas": [], "clasificaciones": []},
                    llm_reasoning="Información insuficiente: título y resumen ausentes o con menos de 20 palabras.",
                    is_info_sufficient=False,
                    execution_time_ms=elapsed_ms,
                    created_at=datetime.utcnow()
                )
                db.add(log_entry)
                db.commit()
            return OCDEClassificationResponse(
                clasificaciones=[],
                is_info_sufficient=False,
                razonamiento_global="Información insuficiente para clasificar en taxonomía OCDE."
            ), log_entry

        # Paso 1: Subáreas
        subareas_text = get_ocde_subareas_formatted()
        p1 = PROMPT_STEP_1_SUBAREA.format(
            title=title_str,
            abstract=abstract_str,
            keywords=keywords_str,
            subareas_list=subareas_text
        )

        log_entry = None
        clasificaciones = []
        razonamiento = ""
        is_sufficient = True
        step1_res = {}
        step2_res = {}

        try:
            req1 = OllamaGenerateRequest(
                model=MODEL_EXACT_VERSION,
                prompt=p1,
                format=Step1Response.model_json_schema(),
                options={"temperature": temperature, "num_ctx": 4096, "seed": 42}
            )
            res1 = await generate_text(req1)
            raw1 = res1.response.strip()
            m1 = re.search(r'(\{.*\})', raw1, re.DOTALL)
            if m1: raw1 = m1.group(1)
            step1_data = Step1Response.model_validate_json(raw1)
            step1_res = step1_data.model_dump()

            if not step1_data.is_info_sufficient or not step1_data.subareas:
                razonamiento = step1_data.razonamiento or "Información insuficiente para determinar subáreas OCDE."
                elapsed_ms = int((time.time() - start_time) * 1000)
                if item_id and db:
                    log_entry = LLMClassificationLog(
                        id_item_enrichment=item_id,
                        classification_type="OCDE",
                        model_version=MODEL_EXACT_VERSION,
                        prompt_template_version=PROMPT_VERSION,
                        prompt=p1[:2000],
                        temperature=temperature,
                        repetition_number=repetition_number,
                        result_json={"step1": step1_res, "step2": None},
                        llm_reasoning=razonamiento,
                        is_info_sufficient=False,
                        execution_time_ms=elapsed_ms,
                        created_at=datetime.utcnow()
                    )
                    db.add(log_entry)
                    db.commit()
                return OCDEClassificationResponse(
                    clasificaciones=[],
                    is_info_sufficient=False,
                    razonamiento_global=razonamiento
                ), log_entry

            codigos_sub = [s.codigo_subarea.strip() for s in step1_data.subareas if s.codigo_subarea]

            # Paso 2: Disciplinas específicas
            disc_text = get_ocde_disciplines_formatted(codigos_sub)
            if not disc_text:
                disc_text = get_ocde_disciplines_formatted()

            p2 = PROMPT_STEP_2_DISCIPLINA.format(
                title=title_str,
                abstract=abstract_str,
                keywords=keywords_str,
                filtered_disciplines_list=disc_text
            )

            req2 = OllamaGenerateRequest(
                model=MODEL_EXACT_VERSION,
                prompt=p2,
                format=Step2Response.model_json_schema(),
                options={"temperature": temperature, "num_ctx": 4096, "seed": 42}
            )
            res2 = await generate_text(req2)
            raw2 = res2.response.strip()
            m2 = re.search(r'(\{.*\})', raw2, re.DOTALL)
            if m2: raw2 = m2.group(1)
            step2_data = Step2Response.model_validate_json(raw2)
            step2_res = step2_data.model_dump()

            razonamiento = f"Paso 1: {step1_data.razonamiento}. Paso 2: {step2_data.razonamiento}".strip()

            # Enriquecer determinísticamente contra Areas_OCDE.xlsx
            for it in step2_data.clasificaciones:
                row_excel = get_ocde_discipline_by_code(it.codigo_disciplina)
                if row_excel:
                    clasificaciones.append(
                        OCDEClassificationItem(
                            codigo_area=row_excel["id_area"],
                            nombre_area=row_excel["nombre_area"],
                            codigo_subarea=row_excel["id_subarea"],
                            nombre_subarea=row_excel["nombre_subarea"],
                            codigo_disciplina=row_excel["id_disciplina"],
                            nombre_disciplina=row_excel["nombre_disciplina"],
                            justificacion=it.justificacion,
                            confidence_score=float(it.confidence_score)
                        )
                    )

            is_sufficient = step2_data.is_info_sufficient and len(clasificaciones) > 0

        except Exception as e:
            elapsed_ms = int((time.time() - start_time) * 1000)
            is_sufficient = False
            razonamiento = f"Error en inferencia o parseo: {e}"
            step1_res = {"error": str(e)}

        elapsed_ms = int((time.time() - start_time) * 1000)
        if item_id and db:
            log_entry = LLMClassificationLog(
                id_item_enrichment=item_id,
                classification_type="OCDE",
                model_version=MODEL_EXACT_VERSION,
                prompt_template_version=PROMPT_VERSION,
                prompt=p2[:2000] if "p2" in locals() else p1[:2000],
                temperature=temperature,
                repetition_number=repetition_number,
                result_json={
                    "step1": step1_res,
                    "step2": step2_res,
                    "clasificaciones_finales": [c.model_dump() for c in clasificaciones]
                },
                llm_reasoning=razonamiento,
                is_info_sufficient=is_sufficient,
                execution_time_ms=elapsed_ms,
                created_at=datetime.utcnow()
            )
            db.add(log_entry)
            db.commit()

        resp = OCDEClassificationResponse(
            clasificaciones=clasificaciones,
            is_info_sufficient=is_sufficient,
            razonamiento_global=razonamiento
        )
        return resp, log_entry

    async def classify_ods_with_logging(
        self,
        item_id: Any,
        title: Optional[str],
        abstract: Optional[str],
        keywords: Optional[str],
        db: Session,
        temperature: float = PRODUCTION_TEMPERATURE,
        repetition_number: int = 1
    ) -> Tuple[ODSClassificationResponse, Optional[LLMClassificationLog]]:
        """Inferencia ODS con registro auditable en LLMClassificationLog."""
        start_time = time.time()
        areas_texto = get_ods_areas_formatted()
        is_sufficient = bool(abstract and len(abstract.strip()) >= 50)

        prompt = f"""
Eres un experto en los 17 Objetivos de Desarrollo Sostenible (ODS) de la ONU (2015).
Tu tarea es clasificar el impacto o contribución socioeconómica/ambiental del siguiente artículo científico:

DATOS DEL ARTÍCULO:
- Título: {title or 'No disponible'}
- Resumen: {abstract or 'No disponible'}
- Palabras clave: {keywords or 'No disponible'}

LISTA DE ODS DISPONIBLES:
{areas_texto}

REGLAS ESTRICTAS:
1. SELECCIONA UN MÁXIMO DE 2 Objetivos de Desarrollo Sostenible representativos.
2. Si el texto es insuficiente para evaluar el impacto global, asigna "is_info_sufficient": false.
3. Responde exclusivamente con un JSON válido con la siguiente estructura:

{{
    "is_info_sufficient": true,
    "razonamiento_global": "Breve explicación de la contribución socioeconómica",
    "clasificaciones": [
        {{
            "numero_ods": "Número del ODS (ej. 3, 6, 13)",
            "nombre_ods": "Nombre del ODS",
            "justificacion": "Breve explicación de 2 oraciones en español",
            "confidence_score": 0.95
        }}
    ]
}}
"""
        ollama_req = OllamaGenerateRequest(
            model=MODEL_EXACT_VERSION.split(":")[0],
            prompt=prompt
        )

        log_entry = None
        clasificaciones = []
        razonamiento = None
        result_json = {}

        try:
            ollama_res = await generate_text(ollama_req)
            elapsed_ms = int((time.time() - start_time) * 1000)
            raw_text = ollama_res.response.strip()

            json_match = re.search(r'(\{.*\})', raw_text, re.DOTALL)
            if json_match:
                raw_text = json_match.group(1)

            result_json = json.loads(raw_text)
            is_sufficient = result_json.get("is_info_sufficient", is_sufficient)
            razonamiento = result_json.get("razonamiento_global", "")

            for item in result_json.get("clasificaciones", [])[:2]:
                clasificaciones.append(
                    ODSClassificationItem(
                        numero_ods=str(item.get("numero_ods", "")),
                        nombre_ods=str(item.get("nombre_ods", "")),
                        justificacion=str(item.get("justificacion", "")),
                        confidence_score=float(item.get("confidence_score", 0.9))
                    )
                )

        except Exception as e:
            elapsed_ms = int((time.time() - start_time) * 1000)
            is_sufficient = False
            razonamiento = f"Error en inferencia o parseo ODS: {e}"
            result_json = {"error": str(e)}

        if item_id:
            log_entry = LLMClassificationLog(
                id_item_enrichment=item_id,
                classification_type="ODS",
                model_version=MODEL_EXACT_VERSION,
                prompt_template_version=PROMPT_VERSION,
                prompt=prompt[:2000],
                temperature=temperature,
                repetition_number=repetition_number,
                result_json=result_json,
                llm_reasoning=razonamiento,
                is_info_sufficient=is_sufficient,
                execution_time_ms=elapsed_ms,
                created_at=datetime.utcnow()
            )
            db.add(log_entry)
            db.commit()

        resp = ODSClassificationResponse(
            clasificaciones=clasificaciones,
            is_info_sufficient=is_sufficient,
            razonamiento_global=razonamiento
        )
        return resp, log_entry

    # Métodos legacy para compatibilidad con endpoints REST existentes
    async def classify_metadata_ocde(self, articulo: MetadataResponse) -> OCDEClassificationResponse:
        resp, _ = await self.classify_ocde_with_logging(
            item_id=None,
            title=articulo.title,
            abstract=articulo.abstract,
            db=None
        )
        resp.articulo = articulo
        return resp

    async def classify_metadata_ods(self, articulo: MetadataResponse) -> ODSClassificationResponse:
        resp, _ = await self.classify_ods_with_logging(
            item_id=None,
            title=articulo.title,
            abstract=articulo.abstract,
            keywords=", ".join(articulo.keywords) if articulo.keywords else None,
            db=None
        )
        resp.articulo = articulo
        return resp
