import os
import json
import shutil
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

from services.ms4_orchestrator.services.dspace_service import DSpaceService
from services.ms4_orchestrator.api.dspace_router import router
from fastapi import FastAPI
from fastapi.testclient import TestClient


class TestDSpaceCacheMS4(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        # Crear un directorio temporal de caché aislado para los tests
        self.test_cache_dir = tempfile.mkdtemp(prefix="test_cache_dspace_")
        self.env_patcher = patch.dict(os.environ, {"DSPACE_CACHE_DIR": self.test_cache_dir})
        self.env_patcher.start()

    def tearDown(self):
        self.env_patcher.stop()
        if os.path.exists(self.test_cache_dir):
            shutil.rmtree(self.test_cache_dir)

    def test_cache_dir_resolution(self):
        """Verifica que cache_dir resuelve la ruta configurada en DSPACE_CACHE_DIR."""
        service = DSpaceService()
        self.assertEqual(service.cache_dir, os.path.abspath(self.test_cache_dir))
        self.assertTrue(os.path.exists(service.cache_dir))

    async def test_get_all_items_writes_and_reads_cache(self):
        """Verifica que get_all_items guarda en caché y luego lee desde disco evitando llamadas de red."""
        service = DSpaceService()

        # Mock de autenticación y respuesta de DSpace
        service.client.authenticate = AsyncMock(return_value="mock_jwt_token")
        mock_raw_data = {
            "_embedded": {
                "searchResult": {
                    "_embedded": {
                        "objects": [
                            {
                                "_embedded": {
                                    "indexableObject": {
                                        "id": "uuid-test-1234",
                                        "metadata": {
                                            "dc.title": [{"value": "Publicación de Prueba 1"}],
                                            "dc.description.abstract": [{"value": "Resumen de prueba"}],
                                            "dc.identifier.doi": [{"value": "10.1000/182"}],
                                            "oaire.resourceType": [{"value": "texto::revista::artículo"}]
                                        }
                                    }
                                }
                            }
                        ]
                    },
                    "page": {
                        "size": 20,
                        "totalElements": 1,
                        "totalPages": 1,
                        "number": 0
                    }
                }
            }
        }
        service.client.get_items = AsyncMock(return_value=mock_raw_data)

        # 1. Primera consulta: debe consultar API y persistir en disco
        res1 = await service.get_all_items(page=0, size=20, use_cache=True)
        self.assertEqual(len(res1["items"]), 1)
        self.assertEqual(res1["items"][0]["uuid"], "uuid-test-1234")
        self.assertEqual(res1["items"][0]["title"], "Publicación de Prueba 1")
        service.client.get_items.assert_called_once()

        # Verificar que se creó el archivo de página y el archivo individual del ítem
        page_file = os.path.join(self.test_cache_dir, "page_0_size_20.json")
        item_file = os.path.join(self.test_cache_dir, "item_uuid-test-1234.json")
        self.assertTrue(os.path.exists(page_file))
        self.assertTrue(os.path.exists(item_file))

        # 2. Segunda consulta: debe leer de disco sin volver a llamar a get_items
        service.client.get_items.reset_mock()
        res2 = await service.get_all_items(page=0, size=20, use_cache=True)
        self.assertEqual(len(res2["items"]), 1)
        self.assertEqual(res2["items"][0]["uuid"], "uuid-test-1234")
        service.client.get_items.assert_not_called()

        # 3. Tercera consulta con use_cache=False: debe saltarse el disco y llamar a la API
        service.client.get_items.reset_mock()
        res3 = await service.get_all_items(page=0, size=20, use_cache=False)
        self.assertEqual(len(res3["items"]), 1)
        service.client.get_items.assert_called_once()

    async def test_get_metadata_uses_cached_item(self):
        """Verifica que get_metadata recupera el ítem instantáneamente si ya está en caché."""
        service = DSpaceService()

        # Guardamos un ítem simulado en la caché
        item_data = {
            "uuid": "uuid-meta-5678",
            "title": "Metadato en Caché",
            "abstract": "Abstract en disco",
            "doi": "10.1234/test",
            "type": "Article",
            "oaire_resourcetype": "texto::revista::artículo",
            "keywords": ["AI", "DSpace"],
            "uri": "https://sic.usach.cl/handle/123",
            "all_metadata": {}
        }
        item_file = os.path.join(self.test_cache_dir, "item_uuid-meta-5678.json")
        with open(item_file, "w", encoding="utf-8") as f:
            json.dump(item_data, f)

        # Mockear cliente para garantizar que no hace llamadas de red
        service.client.authenticate = AsyncMock(side_effect=Exception("No debe autenticar si está en caché"))
        service.client.get_items = AsyncMock(side_effect=Exception("No debe llamar API si está en caché"))

        result = await service.get_metadata("uuid-meta-5678", use_cache=True)
        self.assertEqual(result["uuid"], "uuid-meta-5678")
        self.assertEqual(result["title"], "Metadato en Caché")

    async def test_get_metadata_finds_item_in_cached_page(self):
        """Verifica que get_metadata encuentra un ítem si está dentro de una página previamente descargada."""
        service = DSpaceService()

        # Guardamos una página simulada en disco que contiene el ítem
        page_data = {
            "items": [
                {
                    "uuid": "uuid-page-9999",
                    "title": "Ítem dentro de página",
                    "abstract": "Resumen página",
                    "doi": "10.9999/page",
                    "oaire_resourcetype": "texto::revista::artículo",
                    "keywords": []
                }
            ],
            "page_info": {"totalPages": 1}
        }
        page_file = os.path.join(self.test_cache_dir, "page_0_size_100.json")
        with open(page_file, "w", encoding="utf-8") as f:
            json.dump(page_data, f)

        service.client.authenticate = AsyncMock(side_effect=Exception("No debe llamar API"))
        service.client.get_items = AsyncMock(side_effect=Exception("No debe llamar API"))

        result = await service.get_metadata("uuid-page-9999", use_cache=True)
        self.assertEqual(result["uuid"], "uuid-page-9999")
        self.assertEqual(result["title"], "Ítem dentro de página")

        # Verifica que se generó el item individual en caché para futuras consultas
        item_file = os.path.join(self.test_cache_dir, "item_uuid-page-9999.json")
        self.assertTrue(os.path.exists(item_file))

    def test_cache_stats_and_clear(self):
        """Verifica los métodos de estadísticas y limpieza de caché."""
        service = DSpaceService()

        # Crear archivos de prueba en caché
        with open(os.path.join(self.test_cache_dir, "page_0_size_20.json"), "w") as f:
            f.write('{"test": true}')
        with open(os.path.join(self.test_cache_dir, "item_123.json"), "w") as f:
            f.write('{"test": true}')

        stats = service.get_cache_stats()
        self.assertEqual(stats["total_files"], 2)
        self.assertEqual(stats["page_files"], 1)
        self.assertEqual(stats["item_files"], 1)
        self.assertGreater(stats["size_bytes"], 0)

        # Limpiar sólo ítems
        del_items = service.clear_cache(clear_pages=False, clear_items=True)
        self.assertEqual(del_items["deleted_files"], 1)
        stats2 = service.get_cache_stats()
        self.assertEqual(stats2["page_files"], 1)
        self.assertEqual(stats2["item_files"], 0)

        # Limpiar todo
        del_all = service.clear_cache(clear_pages=True, clear_items=True)
        self.assertEqual(del_all["deleted_files"], 1)
        stats3 = service.get_cache_stats()
        self.assertEqual(stats3["total_files"], 0)

    def test_dspace_router_cache_endpoints(self):
        """Verifica que el router expone los endpoints de caché y acepta use_cache."""
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        # 1. Endpoint de estadísticas de caché
        resp_stats = client.get("/dspace/cache/stats")
        self.assertEqual(resp_stats.status_code, 200)
        data = resp_stats.json()
        self.assertIn("total_files", data)
        self.assertIn("page_files", data)

        # 2. Endpoint para limpiar caché
        resp_clear = client.delete("/dspace/cache")
        self.assertEqual(resp_clear.status_code, 200)
        self.assertIn("deleted_files", resp_clear.json())

        # 3. Endpoint de cola con paginación dinámica y filtros
        from unittest.mock import MagicMock
        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.count.return_value = 45
        mock_query.all.return_value = []
        
        try:
            from common.database import get_db
        except ImportError:
            from services.common.database import get_db

        app.dependency_overrides[get_db] = lambda: mock_db
        
        resp_queue = client.get("/dspace/enrichment-queue?page=1&size=15&q=solar&estado=PENDIENTE,EN_PROCESO")
        self.assertEqual(resp_queue.status_code, 200)
        q_data = resp_queue.json()
        self.assertEqual(q_data["total"], 45)
        self.assertEqual(q_data["page"], 1)
        self.assertEqual(q_data["size"], 15)
        self.assertIn("items", q_data)

    def test_parse_item_funding_and_rights(self):
        """Verifica que _parse_item extraiga funding, rights y licencia adecuadamente."""
        service = DSpaceService()
        raw_item = {
            "_embedded": {
                "indexableObject": {
                    "id": "uuid-fund-1",
                    "metadata": {
                        "dc.title": [{"value": "Estudio de Baterías de Litio"}],
                        "dc.description.sponsorship": [{"value": "FONDECYT Regular 1200001"}],
                        "dc.rights": [{"value": "openAccess"}],
                        "dc.rights.uri": [{"value": "http://creativecommons.org/licenses/by/4.0/"}],
                        "dc.subject": [{"value": "Energía"}, {"value": "Litio"}],
                        "dc.identifier.doi": [{"value": "10.1016/j.est.2024.101"}],
                        "oaire.resourceType": [{"value": "texto::revista::artículo"}]
                    }
                }
            }
        }
        parsed = service._parse_item(raw_item)
        self.assertEqual(parsed["uuid"], "uuid-fund-1")
        self.assertEqual(parsed["funding"], ["FONDECYT Regular 1200001"])
        self.assertEqual(parsed["rights"], "openAccess")
        self.assertEqual(parsed["license"], "cc-by")
        self.assertEqual(parsed["keywords"], ["Energía", "Litio"])

    async def test_count_missing_metadata_multi_falencias(self):
        """Verifica que count_missing_metadata_optimized detecte falencias múltiples (funding, rights, license, keywords)."""
        service = DSpaceService()

        # Mockeamos una página con un artículo al que le falta resumen, funding, derechos y licencia
        page_data = {
            "items": [
                {
                    "uuid": "uuid-item-multi",
                    "title": "Investigación Solar",
                    "doi": "10.1000/solar123",
                    "abstract": "No disponible",
                    "keywords": ["Solar"],
                    "funding": [],
                    "rights": None,
                    "license": None,
                    "oaire_resourcetype": "texto::revista::artículo"
                }
            ],
            "page_info": {"totalPages": 1}
        }
        page_file = os.path.join(self.test_cache_dir, "page_0_size_100.json")
        with open(page_file, "w", encoding="utf-8") as f:
            json.dump(page_data, f)

        service.client.authenticate = AsyncMock(return_value="mock_jwt")
        service.client.get_items = AsyncMock(side_effect=Exception("No debe llamar a la API"))

        res = await service.count_missing_metadata_optimized(save_to_db=False, use_cache=True)
        self.assertGreaterEqual(res["total_candidatos_detectados"], 1)
        
        # Encontrar candidato
        candidato = next(c for c in res["candidatos_enriquecimiento"] if c["dspace_uuid"] == "uuid-item-multi")
        falencias = candidato["tipo_falencia"]
        self.assertIn("SIN_ABSTRACT_CON_DOI", falencias)
        self.assertIn("SIN_FINANCIAMIENTO", falencias)
        self.assertIn("SIN_DERECHOS_ACCESO", falencias)
        self.assertIn("SIN_LICENCIA", falencias)
        self.assertNotIn("SIN_PALABRAS_CLAVE", falencias)

    async def test_enrich_item_populates_metadatos_recuperados(self):
        """Verifica que enrich_item construya y asigne metadatos_recuperados (incluyendo licencia) al item de la BD."""
        from services.ms4_orchestrator.services.enrichment_service import EnrichmentService
        from unittest.mock import MagicMock

        service = EnrichmentService()
        
        # Mock del cliente MS1
        mock_ms1_resp = {
            "best_source": "crossref",
            "consolidated": {
                "abstract": "Abstract recuperado por CrossRef",
                "author_keywords": ["Inteligencia Artificial", "Minimización"],
                "funding_agency": "ANID FONDECYT 1234567",
                "oa_status": "openAccess",
                "license": "http://creativecommons.org/licenses/by/4.0/",
                "doi": "10.1000/182"
            }
        }
        service.ms1_client.retrieve = AsyncMock(return_value=mock_ms1_resp)
        service.ms2_client.classify = AsyncMock(return_value={
            "area_ocde": ["1.2 Ciencias de la Computación"],
            "area_ods": ["9 Industria, Innovación e Infraestructura"]
        })

        mock_item = MagicMock()
        mock_item.id = 1
        mock_item.dspace_uuid = "uuid-test-enrich"
        mock_item.doi = "10.1000/182"
        mock_item.titulo = "Test Publication"
        mock_item.abstract_enriquecido = None
        mock_item.palabras_clave = None
        mock_item.fuente_financiamiento = None
        mock_item.derechos_acceso = None
        mock_item.licencia = None
        mock_item.metadatos_recuperados = None
        mock_item.estado = "PENDIENTE"

        mock_db = MagicMock()

        result = await service.enrich_item(mock_item, mock_db, classify_with_ai=True)

        self.assertEqual(result["estado"], "ENRIQUECIDO")
        self.assertEqual(result["tiene_abstract"], True)
        self.assertEqual(result["licencia"], "cc-by")
        self.assertIsNotNone(result["metadatos_recuperados"])
        self.assertEqual(result["metadatos_recuperados"]["abstract"], "Abstract recuperado por CrossRef")
        self.assertEqual(result["metadatos_recuperados"]["funding"], ["ANID FONDECYT 1234567"])
        self.assertEqual(result["metadatos_recuperados"]["access_rights"], "openAccess")
        self.assertEqual(result["metadatos_recuperados"]["license"], "cc-by")
        self.assertEqual(mock_item.metadatos_recuperados, result["metadatos_recuperados"])
        self.assertEqual(mock_db.commit.call_count, 2)


if __name__ == "__main__":
    unittest.main()

