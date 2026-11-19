import os
import sys
import unittest

sys.path.insert(0, os.path.abspath("services/ms1_retrieval"))
sys.path.insert(0, os.path.abspath("."))

from unittest.mock import MagicMock
from app.models.metadata_model import MetadataResponse
from services.ms1_retrieval.services.retrieval_service import MS1RetrievalWorker
from app.services.retrieval_service import MetadataRetrievalServiceMS1


class TestCandidateSelectionRanking(unittest.TestCase):
    def setUp(self):
        self.worker_ms1 = MS1RetrievalWorker()
        self.service_monolith = MetadataRetrievalServiceMS1()

        # Metadatos simulados del caso real del usuario
        self.meta_crossref_low_conf = MetadataResponse(
            title="Melanoma Epidemiology, Risk Factors, and Clinical Phenotypes",
            authors=["Elena B.", "David E."],
            doi="10.5772/23293",
            year=2011,
            source="Crossref",
            abstract=None,
            keywords=["melanoma", "risk factors"]
        )

        self.meta_europepmc_high_conf = MetadataResponse(
            title="[Epidemiology and clinical features of malignant melanoma. Analysis of 274 cases].",
            authors=["Sapunar Z J", "Pantoja A Á", "Marín D L", "Ferrer-Rosende P."],
            doi="10.4067/s0034-98872022001201585",
            year=2022,
            source="Europe PMC",
            abstract="<h4>Background</h4>Malignant melanoma (MM) is the most fatal cutaneous neoplasm...",
            keywords=["melanoma", "incidence"]
        )

    def test_ms1_retrieval_worker_prioritizes_higher_confidence_source(self):
        """
        Verifica que cuando Europe PMC tiene un match_score mayor (1.0 vs 0.44),
        MS1RetrievalWorker consolide el DOI y abstract de Europe PMC, descartando Crossref.
        """
        results_by_source = {
            "Crossref": self.meta_crossref_low_conf,
            "Europe PMC": self.meta_europepmc_high_conf
        }
        match_scores = {
            "Crossref": 0.4411764705882353,
            "Europe PMC": 1.0
        }

        ranked = self.worker_ms1._rank_sources(
            results_by_source,
            match_scores,
            preferred_order=["Crossref", "OpenAlex", "Semantic Scholar", "Europe PMC"]
        )
        self.assertEqual(ranked, ["Europe PMC"])

        consolidated = self.worker_ms1._consolidate(
            results_by_source,
            best_doi=None,
            match_scores=match_scores
        )

        self.assertEqual(consolidated["doi"], "10.4067/s0034-98872022001201585")
        self.assertEqual(consolidated["abstract_source"], "Europe PMC")
        self.assertIn("Malignant melanoma", consolidated["abstract"])
        # Verificar que no contamina con keywords de la fuente descartada (< 0.60)
        self.assertNotIn("risk factors", consolidated.get("author_keywords", "") or "")

    def test_monolith_retrieval_service_prioritizes_higher_confidence_source(self):
        """
        Verifica que el servicio monolítico aplique exactamente la misma lógica de confianza.
        """
        results_by_source = {
            "Crossref": self.meta_crossref_low_conf,
            "Europe PMC": self.meta_europepmc_high_conf
        }
        match_scores = {
            "Crossref": 0.4411764705882353,
            "Europe PMC": 1.0
        }

        ranked = self.service_monolith._rank_sources(
            results_by_source,
            match_scores,
            preferred_order=["Crossref", "OpenAlex", "Semantic Scholar", "Europe PMC"]
        )
        self.assertEqual(ranked, ["Europe PMC"])

        consolidated = self.service_monolith._consolidate_metadata(
            results_by_source,
            best_doi=None,
            match_scores=match_scores
        )

        self.assertEqual(consolidated["doi"], "10.4067/s0034-98872022001201585")
        self.assertEqual(consolidated["abstract_source"], "Europe PMC")
        self.assertIn("Malignant melanoma", consolidated["abstract"])

    def test_tie_breaking_uses_academic_priority(self):
        """
        Verifica que si dos fuentes tienen la misma confianza (ej. 1.0 ambos),
        se aplique la jerarquía académica como desempate (Crossref > Europe PMC).
        """
        meta_crossref_perfect = MetadataResponse(
            title="[Epidemiology and clinical features of malignant melanoma. Analysis of 274 cases].",
            authors=["Sapunar Z J"],
            doi="10.4067/s0034-crossref",
            year=2022,
            source="Crossref",
            abstract="Resumen oficial de Crossref con suficiente longitud para ser válido...",
            keywords=["melanoma"]
        )
        results_by_source = {
            "Crossref": meta_crossref_perfect,
            "Europe PMC": self.meta_europepmc_high_conf
        }
        match_scores = {
            "Crossref": 1.0,
            "Europe PMC": 1.0
        }

        ranked = self.worker_ms1._rank_sources(
            results_by_source,
            match_scores,
            preferred_order=["Crossref", "OpenAlex", "Semantic Scholar", "Europe PMC"]
        )
        # En empate exacto, Crossref tiene precedencia académica
        self.assertEqual(ranked[0], "Crossref")
        self.assertEqual(ranked[1], "Europe PMC")

        consolidated = self.worker_ms1._consolidate(
            results_by_source,
            best_doi=None,
            match_scores=match_scores
        )
        self.assertEqual(consolidated["doi"], "10.4067/s0034-crossref")
        self.assertEqual(consolidated["abstract_source"], "Crossref")

    def test_preserves_existing_doi_when_provided(self):
        """
        Verifica que si ya existía un DOI validado previo, este se conserve intacto.
        """
        results_by_source = {
            "Europe PMC": self.meta_europepmc_high_conf
        }
        match_scores = {
            "Europe PMC": 1.0
        }
        consolidated = self.worker_ms1._consolidate(
            results_by_source,
            best_doi="10.9999/existing-doi",
            match_scores=match_scores
        )
        self.assertEqual(consolidated["doi"], "10.9999/existing-doi")

    def test_multi_source_ranking_gradation(self):
        """
        Verifica la gradación de múltiples fuentes según match_score:
        Europe PMC (0.95) > OpenAlex (0.90) > Crossref (0.75).
        """
        results_by_source = {
            "Crossref": self.meta_crossref_low_conf,
            "Europe PMC": self.meta_europepmc_high_conf,
            "OpenAlex": MetadataResponse(
                title="Paper OpenAlex",
                authors=["Autor"],
                doi="10.1111/openalex",
                source="OpenAlex"
            )
        }
        match_scores = {
            "Crossref": 0.75,
            "OpenAlex": 0.90,
            "Europe PMC": 0.95
        }
        ranked = self.worker_ms1._rank_sources(
            results_by_source,
            match_scores,
            preferred_order=["Crossref", "OpenAlex", "Europe PMC"]
        )
        self.assertEqual(ranked, ["Europe PMC", "OpenAlex", "Crossref"])

    def test_record_completitud_calculation(self):
        """
        Verifica el cálculo del porcentaje de completitud real:
        100% cuando los 6 metadatos están presentes (financiamiento, resumen,
        palabras clave, área ocde, área ods, derechos de acceso).
        """
        from services.ms4_orchestrator.api.dspace_router import calculate_record_completitud
        from services.ms4_orchestrator.models import DSpaceEnrichmentQueue

        # Caso 1: Los 6 metadatos presentes -> 100%
        item_full = DSpaceEnrichmentQueue(
            id=1,
            dspace_uuid="uuid-1",
            titulo="Test Full",
            abstract_enriquecido="Resumen enriquecido completo con suficiente longitud.",
            palabras_clave=["oncología", "melanoma"],
            fuente_financiamiento=["FONDECYT 123456"],
            derechos_acceso="openAccess",
            area_ocde=["3. Ciencias Médicas"],
            area_ods=["ODS 3: Salud"],
            tipo_falencia="SIN_ABSTRACT"
        )
        comp, comp_pre = calculate_record_completitud(item_full)
        self.assertEqual(comp, 100)

        # Caso 2: 3 metadatos presentes (resumen, keywords, derechos de acceso) -> 50%
        item_half = DSpaceEnrichmentQueue(
            id=2,
            dspace_uuid="uuid-2",
            titulo="Test Half",
            abstract_enriquecido="Resumen enriquecido completo con suficiente longitud.",
            palabras_clave=["oncología"],
            derechos_acceso="closedAccess",
            tipo_falencia="SIN_FINANCIAMIENTO"
        )
        comp_half, comp_pre_half = calculate_record_completitud(item_half)
        self.assertEqual(comp_half, 50)  # 3/6 = 50%

        # Caso 3: Registro vacío sin ningún metadato enriquecido -> 0%
        item_empty = DSpaceEnrichmentQueue(
            id=3,
            dspace_uuid="uuid-3",
            titulo="Test Empty",
            tipo_falencia="SIN_ABSTRACT, SIN_FINANCIAMIENTO, SIN_PALABRAS_CLAVE, SIN_DERECHOS_ACCESO"
        )
        comp_empty, _ = calculate_record_completitud(item_empty)
        self.assertEqual(comp_empty, 0)


if __name__ == "__main__":
    unittest.main()
