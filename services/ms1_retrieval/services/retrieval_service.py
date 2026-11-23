import time
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

try:
    from models import CandidateMatch, ExternalAPISource, RetrievalResponse, CandidateMetadataDTO
    from clients.crossref_client import get_by_doi_crossref, search_crossref
    from clients.openalex_client import OpenAlexClient, get_by_doi_openalex
    from clients.unpaywall_client import get_metadata_by_doi_unpaywall
    from clients.europe_pmc_client import get_by_doi_europe_pmc, search_europe_pmc
    from clients.semantic_scholar_client import get_by_doi_semantic_scholar, search_semantic_scholar, get_by_exact_title_semantic_scholar
    from services.matching_service import calculate_similarity, evaluate_doi_match, evaluate_no_doi_match
except ImportError:
    from services.ms1_retrieval.models import CandidateMatch, ExternalAPISource, RetrievalResponse, CandidateMetadataDTO
    from services.ms1_retrieval.clients.crossref_client import get_by_doi_crossref, search_crossref
    from services.ms1_retrieval.clients.openalex_client import OpenAlexClient, get_by_doi_openalex
    from services.ms1_retrieval.clients.unpaywall_client import get_metadata_by_doi_unpaywall
    from services.ms1_retrieval.clients.europe_pmc_client import get_by_doi_europe_pmc, search_europe_pmc
    from services.ms1_retrieval.clients.semantic_scholar_client import get_by_doi_semantic_scholar, search_semantic_scholar, get_by_exact_title_semantic_scholar
    from services.ms1_retrieval.services.matching_service import calculate_similarity, evaluate_doi_match, evaluate_no_doi_match


class MS1RetrievalWorker:
    """
    Lógica de recuperación y validación para MS1.
    Escribe exclusivamente en Candidate_Match y External_API_Source.
    """

    def __init__(self):
        self.openalex_client = OpenAlexClient()

    def _get_external_source_id(self, db: Session, source_name: str) -> int:
        src = db.query(ExternalAPISource).filter(ExternalAPISource.name == source_name).first()
        if not src:
            src = ExternalAPISource(name=source_name, base_url="", is_active=True)
            db.add(src)
            db.commit()
            db.refresh(src)
        return src.id

    async def execute_retrieval(
        self,
        item_id: uuid.UUID,
        doi: Optional[str],
        title: Optional[str],
        db: Session
    ) -> Dict[str, Any]:
        results_by_source = {}
        query_statuses = {}
        match_scores = {}

        has_doi = bool(doi and doi.strip())
        doi_clean = doi.strip() if has_doi else None

        sources = ["Crossref", "OpenAlex", "Unpaywall", "Semantic Scholar", "Europe PMC"]

        for source_name in sources:
            source_id = self._get_external_source_id(db, source_name)
            meta = None
            query_result = "sin_datos"
            score = 0.0
            candidate_doi = doi_clean

            try:
                if has_doi:
                    if source_name == "Crossref":
                        meta = await get_by_doi_crossref(doi_clean)
                    elif source_name == "OpenAlex":
                        meta = await get_by_doi_openalex(doi_clean)
                    elif source_name == "Unpaywall":
                        meta = await get_metadata_by_doi_unpaywall(doi_clean)
                    elif source_name == "Semantic Scholar":
                        meta = await get_by_doi_semantic_scholar(doi_clean)
                    elif source_name == "Europe PMC":
                        meta = await get_by_doi_europe_pmc(doi_clean)
                else:
                    if title:
                        if source_name == "Crossref":
                            res_list = await search_crossref(title, limit=1)
                            meta = res_list[0] if res_list else None
                        elif source_name == "OpenAlex":
                            candidates = await self.openalex_client.search_candidates_by_title(title, limit=1)
                            if candidates:
                                meta = candidates[0].get("metadata")
                                candidate_doi = meta.doi if meta else None
                        elif source_name == "Semantic Scholar":
                            # Priorizar coincidencia exacta de título (/paper/search/match)
                            meta = await get_by_exact_title_semantic_scholar(title)
                            if not meta:
                                res_list = await search_semantic_scholar(title, limit=1)
                                meta = res_list[0] if res_list else None
                        elif source_name == "Europe PMC":
                            res_list = await search_europe_pmc(title, limit=1)
                            meta = res_list[0] if res_list else None

                if meta:
                    query_result = "exitosa"
                    candidate_doi = meta.doi or candidate_doi
                    score = calculate_similarity(title, meta.title)
                else:
                    query_result = "sin_datos"

            except Exception as e:
                query_result = "fallida"
                print(f"[MS1] Error consultando {source_name}: {e}")

            raw_json = meta.model_dump() if meta else {"error": query_result}
            cm = CandidateMatch(
                id_item_enrichment=item_id,
                id_external_source=source_id,
                candidate_doi=candidate_doi,
                match_score=score,
                query_result=query_result,
                raw_metadata_json=raw_json,
                retrieved_at=datetime.utcnow()
            )
            db.add(cm)

            results_by_source[source_name] = meta
            query_statuses[source_name] = query_result
            match_scores[source_name] = score

        db.commit()

        # Evaluación de umbrales y selección de mejor fuente priorizando match_score
        ranked_general = self._rank_sources(
            results_by_source,
            match_scores,
            preferred_order=["Crossref", "OpenAlex", "Semantic Scholar", "Europe PMC", "Unpaywall"]
        )
        best_source = ranked_general[0] if ranked_general else None
        max_score = match_scores.get(best_source, 0.0) if best_source else 0.0

        if has_doi:
            if max_score > 0.0 and max_score < 0.85:
                outcome = "COINCIDENCIA_DUDOSA"
            elif max_score >= 0.85:
                outcome = "ALTA_COINCIDENCIA"
            else:
                outcome = "SIN_DATOS"
        else:
            if max_score >= 0.95:
                outcome = "ALTA_COINCIDENCIA"
            elif max_score >= 0.70:
                outcome = "COINCIDENCIA_DUDOSA"
            else:
                outcome = "DESCARTADA"

        consolidated = self._consolidate(results_by_source, doi_clean, match_scores)

        return {
            "outcome": outcome,
            "max_score": max_score,
            "best_source": best_source,
            "consolidated": consolidated,
            "query_statuses": query_statuses
        }

    def _rank_sources(
        self,
        results_by_source: Dict[str, Any],
        match_scores: Optional[Dict[str, float]] = None,
        preferred_order: Optional[List[str]] = None
    ) -> List[str]:
        """
        Ordena las fuentes disponibles según:
        1. Intervalo de confianza (match_score descendente).
        2. En caso de empate o puntajes prácticamente idénticos dentro del redondeo a 2 decimales,
           se utiliza el orden de prioridad académica como criterio de desempate.
        3. Si existe una fuente de confianza alta o moderada (>= 0.70), descarta fuentes con score < 0.60
           para evitar contaminación de metadatos con artículos no coincidentes.
        """
        if preferred_order is None:
            preferred_order = ["Crossref", "OpenAlex", "Semantic Scholar", "Europe PMC", "Unpaywall"]

        scores = match_scores or {}

        valid_sources = [s for s in preferred_order if results_by_source.get(s)]
        for s in results_by_source:
            if results_by_source.get(s) and s not in valid_sources:
                valid_sources.append(s)

        if not valid_sources:
            return []

        max_score = max((scores.get(s, 0.0) for s in valid_sources), default=0.0)
        if max_score >= 0.70:
            filtered = [s for s in valid_sources if scores.get(s, 0.0) >= 0.60]
            if filtered:
                valid_sources = filtered

        def sort_key(s: str):
            score = scores.get(s, 0.0)
            pref_idx = preferred_order.index(s) if s in preferred_order else 999
            return (-round(score, 2), pref_idx)

        return sorted(valid_sources, key=sort_key)

    def _consolidate(
        self,
        results_by_source: Dict[str, Any],
        best_doi: Optional[str],
        match_scores: Optional[Dict[str, float]] = None
    ) -> Dict[str, Any]:
        scores = match_scores or {}

        # Abstract: priorizar fuente con mayor confianza, desempate académico
        abstract = None
        abstract_source = None
        ranked_abstract_sources = self._rank_sources(
            results_by_source,
            scores,
            preferred_order=["Crossref", "OpenAlex", "Semantic Scholar", "Europe PMC"]
        )
        for s in ranked_abstract_sources:
            meta = results_by_source.get(s)
            if meta and getattr(meta, "abstract", None) and len(meta.abstract.strip()) > 20:
                abstract = meta.abstract.strip()
                abstract_source = s
                break

        # Palabras clave del autor (filtrando fuentes descartadas por bajo score)
        author_kws = set()
        ranked_kws_sources = self._rank_sources(
            results_by_source,
            scores,
            preferred_order=["Crossref", "OpenAlex", "Semantic Scholar", "Europe PMC"]
        )
        for s in ranked_kws_sources:
            meta = results_by_source.get(s)
            if meta:
                kws = getattr(meta, "author_keywords", None) or getattr(meta, "keywords", None) or []
                for k in kws:
                    if k and len(k.strip()) > 2:
                        author_kws.add(k.strip())

        # Conceptos automáticos algorítmicos (OpenAlex, sólo si tiene confianza suficiente)
        automated_concepts = set()
        ranked_openalex = self._rank_sources(
            results_by_source,
            scores,
            preferred_order=["OpenAlex"]
        )
        if "OpenAlex" in ranked_openalex:
            openalex_meta = results_by_source.get("OpenAlex")
            if openalex_meta and getattr(openalex_meta, "automated_concepts", None):
                for c in openalex_meta.automated_concepts:
                    if c:
                        automated_concepts.add(c.strip())

        # Financiamiento desglosado
        funding_agency = None
        funding_id = None
        funding_grant = None
        ranked_funding_sources = self._rank_sources(
            results_by_source,
            scores,
            preferred_order=["Crossref", "OpenAlex", "Europe PMC"]
        )
        for s in ranked_funding_sources:
            meta = results_by_source.get(s)
            if meta and (getattr(meta, "funding_agency", None) or getattr(meta, "funding_grant_number", None) or getattr(meta, "funding_id", None)):
                funding_agency = getattr(meta, "funding_agency", None)
                funding_id = getattr(meta, "funding_id", None)
                funding_grant = getattr(meta, "funding_grant_number", None)
                break

        # Acceso abierto, Licencia y Versión
        oa_status = None
        license_val = None
        version_type = None
        ranked_oa_sources = self._rank_sources(
            results_by_source,
            scores,
            preferred_order=["Unpaywall", "OpenAlex", "Crossref", "Europe PMC"]
        )
        for s in ranked_oa_sources:
            meta = results_by_source.get(s)
            if meta and (getattr(meta, "oa_status", None) or getattr(meta, "license", None) or getattr(meta, "version_type", None)):
                oa_status = oa_status or getattr(meta, "oa_status", None)
                license_val = license_val or getattr(meta, "license", None)
                version_type = version_type or getattr(meta, "version_type", None)

        # DOI: si no se proporcionó uno original, se prioriza el DOI de la fuente con mayor match_score
        final_doi = best_doi
        if not final_doi:
            ranked_doi_sources = self._rank_sources(
                results_by_source,
                scores,
                preferred_order=["Crossref", "OpenAlex", "Semantic Scholar", "Europe PMC"]
            )
            for s in ranked_doi_sources:
                meta = results_by_source.get(s)
                if meta and getattr(meta, "doi", None):
                    final_doi = meta.doi
                    break

        return {
            "doi": final_doi,
            "abstract": abstract,
            "abstract_source": abstract_source,
            "author_keywords": ", ".join(sorted(author_kws)) if author_kws else None,
            "automated_concepts": ", ".join(sorted(automated_concepts)) if automated_concepts else None,
            "funding_agency": funding_agency,
            "funding_id": funding_id,
            "funding_grant_number": funding_grant,
            "oa_status": oa_status,
            "license": license_val,
            "version_type": version_type
        }

