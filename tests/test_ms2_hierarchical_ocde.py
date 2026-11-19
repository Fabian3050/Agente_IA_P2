import os
import sys
import unittest
import uuid
from unittest.mock import AsyncMock, patch, MagicMock

sys.path.insert(0, os.path.abspath("."))

from services.ms2_classification.services.ocde_service import (
    get_ocde_subareas,
    get_ocde_subareas_formatted,
    get_ocde_disciplines_for_subareas,
    get_ocde_disciplines_formatted,
    get_ocde_discipline_by_code
)
from services.ms2_classification.services.classification_service import (
    MS2ClassificationWorker,
    Step1Response,
    Step2Response,
    SubareaPick,
    DisciplinaPick
)
from services.ms2_classification.services.ollama_client import OllamaResponse


class TestMS2HierarchicalOCDE(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.worker = MS2ClassificationWorker()

    def test_ocde_taxonomy_structure(self):
        """Verifica que el catálogo oficial tenga exactamente las 42 subáreas y la jerarquía correcta."""
        subareas = get_ocde_subareas()
        self.assertEqual(len(subareas), 42)

        # Verificar formateo del Paso 1
        subareas_text = get_ocde_subareas_formatted()
        self.assertIn("1.02.00: Computer and information sciences (Área: Natural sciences)", subareas_text)
        self.assertIn("3.02.00: Clinical medicine (Área: Medical and Health sciences)", subareas_text)

        # Verificar filtrado del Paso 2 para 1.02.00
        discs_comp = get_ocde_disciplines_for_subareas(["1.02.00"])
        self.assertEqual(len(discs_comp), 3)
        codes = [d["id_disciplina"] for d in discs_comp]
        self.assertIn("1.02.01", codes)
        self.assertIn("1.02.02", codes)
        self.assertIn("1.02.03", codes)

        # Formateo del Paso 2
        disc_text = get_ocde_disciplines_formatted(["1.02.00"])
        self.assertIn("1.02.01 | Computer sciences (Subárea: Computer and information sciences)", disc_text)

        # Búsqueda determinista por código
        disc = get_ocde_discipline_by_code("1.02.01")
        self.assertIsNotNone(disc)
        self.assertEqual(disc["id_area"], "1.00.00")
        self.assertEqual(disc["nombre_area"], "Natural sciences")
        self.assertEqual(disc["id_subarea"], "1.02.00")
        self.assertEqual(disc["nombre_subarea"], "Computer and information sciences")
        self.assertEqual(disc["id_disciplina"], "1.02.01")
        self.assertEqual(disc["nombre_disciplina"], "Computer sciences")

    @patch("services.ms2_classification.services.classification_service.generate_text")
    async def test_hierarchical_two_step_classification_flow(self, mock_generate_text):
        """
        Simula el flujo completo en 2 pasos:
        Paso 1: Ollama elige 1.02.00 (Computer and information sciences).
        Paso 2: Ollama elige 1.02.01 (Computer sciences) a partir de la lista filtrada.
        """
        step1_json = '{"is_info_sufficient": true, "razonamiento": "Artículo sobre algoritmos de visión por computador.", "subareas": [{"codigo_subarea": "1.02.00", "justificacion": "Trata sobre ciencias de la computación."}]}'
        step2_json = '{"is_info_sufficient": true, "razonamiento": "Desarrollo de nuevas redes neuronales.", "clasificaciones": [{"codigo_disciplina": "1.02.01", "prioridad": 1, "justificacion": "Metodología central de ciencias de la computación.", "confidence_score": 0.94}]}'

        mock_generate_text.side_effect = [
            OllamaResponse(response=step1_json),
            OllamaResponse(response=step2_json)
        ]

        mock_db = MagicMock()
        item_id = uuid.uuid4()

        items, is_suff, reason, elapsed = await self.worker._classify_ocde(
            item_id=item_id,
            title="Deep Learning Framework for Real-Time Image Segmentation",
            abstract="We propose a novel convolutional neural network architecture tailored for real-time semantic segmentation on embedded devices with high accuracy.",
            keywords="deep learning, neural networks, computer vision",
            db=mock_db,
            temperature=0.0,
            repetition_number=1
        )

        self.assertTrue(is_suff)
        self.assertEqual(len(items), 1)
        item = items[0]
        self.assertEqual(item.codigo_area, "1.00.00")
        self.assertEqual(item.nombre_area, "Natural sciences")
        self.assertEqual(item.codigo_subarea, "1.02.00")
        self.assertEqual(item.nombre_subarea, "Computer and information sciences")
        self.assertEqual(item.codigo_disciplina, "1.02.01")
        self.assertEqual(item.nombre_disciplina, "Computer sciences")
        self.assertEqual(item.confidence_score, 0.94)

        # Se llamó a Ollama dos veces consecutivas
        self.assertEqual(mock_generate_text.call_count, 2)
        # Se guardó bitácora en la BD
        self.assertTrue(mock_db.add.called)
        self.assertTrue(mock_db.commit.called)

    async def test_insufficient_information_handling(self):
        """Verifica que con textos insuficientes no se llame al modelo y se retorne is_info_sufficient=False."""
        mock_db = MagicMock()
        item_id = uuid.uuid4()

        items, is_suff, reason, elapsed = await self.worker._classify_ocde(
            item_id=item_id,
            title="Short",
            abstract="",
            keywords="",
            db=mock_db,
            temperature=0.0,
            repetition_number=1
        )

        self.assertFalse(is_suff)
        self.assertEqual(items, [])
        self.assertIn("insuficiente", reason.lower())


if __name__ == "__main__":
    unittest.main()
