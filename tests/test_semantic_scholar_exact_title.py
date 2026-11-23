import os
import sys
import unittest
from unittest.mock import AsyncMock, patch, MagicMock
import httpx

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

SERVICES_DIR = os.path.join(PROJECT_ROOT, "services")
if SERVICES_DIR not in sys.path:
    sys.path.insert(0, SERVICES_DIR)

MS1_DIR = os.path.join(PROJECT_ROOT, "services", "ms1_retrieval")
if MS1_DIR not in sys.path:
    sys.path.insert(0, MS1_DIR)

from services.ms1_retrieval.clients.semantic_scholar_client import (
    get_by_exact_title_semantic_scholar,
    search_semantic_scholar,
    _parse_semantic_scholar_item
)
from services.ms1_retrieval.models.metadata_model import MetadataResponse
from services.ms4_orchestrator.models import DSpaceEnrichmentQueue


class TestSemanticScholarExactTitle(unittest.IsolatedAsyncioTestCase):

    async def test_get_by_exact_title_semantic_scholar_match_success(self):
        """
        Verifica que el nuevo método consulte /paper/search/match y parsee
        correctamente los metadatos completos devueltos por Semantic Scholar.
        """
        mock_response_data = {
            "paperId": "abcdef1234567890",
            "matchScore": 142.5,
            "title": "Attention Is All You Need",
            "year": 2017,
            "authors": [
                {"authorId": "1", "name": "Ashish Vaswani"},
                {"authorId": "2", "name": "Noam Shazeer"}
            ],
            "externalIds": {
                "DOI": "10.48550/arXiv.1706.03762",
                "ArXiv": "1706.03762"
            },
            "url": "https://www.semanticscholar.org/paper/abcdef1234567890",
            "abstract": "The dominant sequence transduction models are based on complex recurrent or convolutional neural networks...",
            "s2FieldsOfStudy": [
                {"category": "Computer Science", "source": "s2-fos-model"}
            ],
            "openAccessPdf": {
                "url": "https://arxiv.org/pdf/1706.03762.pdf",
                "status": "GOLD"
            }
        }

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_response_data

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_resp
            result = await get_by_exact_title_semantic_scholar("Attention Is All You Need")

            self.assertIsNotNone(result)
            self.assertEqual(result.title, "Attention Is All You Need")
            self.assertEqual(result.doi, "10.48550/arXiv.1706.03762")
            self.assertEqual(result.year, 2017)
            self.assertEqual(result.source, "semanticscholar")
            self.assertIn("Ashish Vaswani", result.authors)
            self.assertTrue(result.abstract.startswith("The dominant sequence"))
            self.assertEqual(result.keywords, ["Computer Science"])
            self.assertEqual(result.oa_status, "GOLD")

            # Verifica que la URL llamada sea exactamente /paper/search/match
            args, kwargs = mock_get.call_args
            self.assertEqual(args[0], "https://api.semanticscholar.org/graph/v1/paper/search/match")
            self.assertEqual(kwargs["params"]["query"], "Attention Is All You Need")

    async def test_get_by_exact_title_semantic_scholar_fallback_to_paper_title(self):
        """
        Verifica que si /paper/search/match responde 404, el cliente intente
        el fallback secundario /paper/title:{title}.
        """
        mock_404_resp = MagicMock()
        mock_404_resp.status_code = 404

        mock_200_resp = MagicMock()
        mock_200_resp.status_code = 200
        mock_200_resp.json.return_value = {
            "title": "Deep Learning for Visual Understanding",
            "year": 2020,
            "authors": [{"name": "Y. LeCun"}],
            "externalIds": {"DOI": "10.1000/182"},
            "abstract": "A review of modern deep learning methodologies.",
            "s2FieldsOfStudy": []
        }

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = [mock_404_resp, mock_200_resp]
            result = await get_by_exact_title_semantic_scholar("Deep Learning for Visual Understanding")

            self.assertIsNotNone(result)
            self.assertEqual(result.title, "Deep Learning for Visual Understanding")
            self.assertEqual(result.doi, "10.1000/182")
            self.assertEqual(mock_get.call_count, 2)

    async def test_get_by_exact_title_semantic_scholar_empty_or_short(self):
        """Verifica que títulos vacíos o demasiado cortos (< 4 caracteres) no llamen a la API."""
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            r1 = await get_by_exact_title_semantic_scholar("")
            r2 = await get_by_exact_title_semantic_scholar("   ")
            r3 = await get_by_exact_title_semantic_scholar("AI")
            self.assertIsNone(r1)
            self.assertIsNone(r2)
            self.assertIsNone(r3)
            mock_get.assert_not_called()

    async def test_retrieval_worker_invokes_exact_title_semantic_scholar(self):
        """
        Verifica que MS1RetrievalWorker priorice get_by_exact_title_semantic_scholar
        al consultar Semantic Scholar por título.
        """
        from services.ms1_retrieval.services.retrieval_service import MS1RetrievalWorker

        worker = MS1RetrievalWorker()
        mock_db = MagicMock()

        mock_meta = MetadataResponse(
            title="Solar Energy Cell Materials",
            authors=["Dr. Solar"],
            doi="10.1016/solar.2023",
            source="semanticscholar",
            abstract="High efficiency solar cells...",
            keywords=["Renewable Energy"]
        )

        with patch("services.ms1_retrieval.services.retrieval_service.get_by_exact_title_semantic_scholar", new_callable=AsyncMock) as mock_exact:
            mock_exact.return_value = mock_meta
            with patch.object(worker, "_get_external_source_id", return_value=1):
                res = await worker.execute_retrieval(
                    item_id="00000000-0000-0000-0000-000000000001",
                    doi=None,
                    title="Solar Energy Cell Materials",
                    db=mock_db
                )

            mock_exact.assert_called_once_with("Solar Energy Cell Materials")
            self.assertEqual(res["outcome"], "ALTA_COINCIDENCIA")
            self.assertEqual(res["query_statuses"]["Semantic Scholar"], "exitosa")
            self.assertEqual(res["best_source"], "Semantic Scholar")

    async def test_enrichment_service_queue_enrichment_via_exact_semantic_scholar(self):
        """
        Verifica que al enriquecer un ítem de la cola (DSpaceEnrichmentQueue) que carece de abstract,
        la coincidencia exacta de título en Semantic Scholar recupere y persista abstract, DOI y keywords.
        """
        from app.services.enrichment_service import EnrichmentService

        service = EnrichmentService()
        mock_db = MagicMock()

        item = DSpaceEnrichmentQueue(
            id=101,
            dspace_uuid="uuid-ss-101",
            titulo="Quantum Computing Advancements in 2024",
            doi=None,
            abstract_enriquecido=None,
            palabras_clave=None,
            tipo_falencia="SIN_ABSTRACT_SIN_DOI",
            intentos=0
        )

        mock_ss_meta = MetadataResponse(
            title="Quantum Computing Advancements in 2024",
            authors=["Alice Q."],
            doi="10.1103/quantum.2024",
            source="semanticscholar",
            abstract="Quantum computing has demonstrated groundbreaking computational speedups...",
            keywords=["Quantum Physics", "Algorithms"]
        )

        with patch("app.clients.semantic_scholar_client.get_by_exact_title_semantic_scholar", new_callable=AsyncMock) as mock_exact:
            mock_exact.return_value = mock_ss_meta
            with patch.object(service.classification_service, "classify_item_for_enrichment", new_callable=AsyncMock) as mock_classify:
                mock_classify.return_value = {
                    "area_ocde": ["1.03 Ciencias Físicas"],
                    "area_ods": ["9 Industria, Innovación e Infraestructura"]
                }
                result = await service.enrich_item(item, mock_db, classify_with_ai=True)

        self.assertIn(result["estado"], ["ENRIQUECIDO", "ENRIQUECIDO_FUENTES", "COMPLETO"])
        self.assertEqual(item.abstract_enriquecido, "Quantum computing has demonstrated groundbreaking computational speedups...")
        self.assertEqual(item.doi, "10.1103/quantum.2024")
        self.assertIn("Quantum Physics", item.palabras_clave)
        self.assertIn("semanticscholar", item.fuente_enriquecimiento)


if __name__ == "__main__":
    unittest.main()
