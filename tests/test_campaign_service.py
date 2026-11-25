import os
import sys
import unittest
from unittest import mock
from datetime import datetime

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SERVICES_DIR = os.path.join(PROJECT_ROOT, "services")

if SERVICES_DIR not in sys.path:
    sys.path.insert(0, SERVICES_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from services.ms4_orchestrator.services.campaign_service import (
    AnnualCampaignManager,
    compute_next_scheduled_run,
    ANNUAL_CAMPAIGN_MONTH,
    ANNUAL_CAMPAIGN_DAY,
    ANNUAL_CAMPAIGN_HOUR
)


class TestCampaignService(unittest.TestCase):

    def setUp(self):
        self.manager = AnnualCampaignManager()

    def test_compute_next_scheduled_run(self):
        """Verifica que el cálculo de la próxima fecha apunte a abril (mes 4, día 15, 02:00 hrs)."""
        next_run = compute_next_scheduled_run()
        self.assertIsInstance(next_run, datetime)
        self.assertEqual(next_run.month, ANNUAL_CAMPAIGN_MONTH)
        self.assertEqual(next_run.day, ANNUAL_CAMPAIGN_DAY)
        self.assertEqual(next_run.hour, ANNUAL_CAMPAIGN_HOUR)
        self.assertGreaterEqual(next_run, datetime.now())

    def test_get_status_initial(self):
        """Verifica que el estado inicial de la campaña sea IDLE y exponga métricas y calendario."""
        status = self.manager.get_status()
        self.assertFalse(status["is_running"])
        self.assertEqual(status["status"], "IDLE")
        self.assertEqual(status["total_items"], 0)
        self.assertEqual(status["processed_items"], 0)
        self.assertIn("next_scheduled_run", status)
        self.assertIn("15/04", status["next_scheduled_run_formatted"])
        self.assertTrue(status["schedule_config"]["enabled"])

    def test_stop_campaign_when_not_running(self):
        """Verifica el comportamiento cuando se solicita detener una campaña no activa."""
        res = self.manager.stop_campaign()
        self.assertFalse(res["ok"])
        self.assertIn("No hay ninguna campaña", res["message"])

    def test_stop_campaign_when_running(self):
        """Verifica que stop_campaign marque stop_requested cuando está corriendo."""
        self.manager.is_running = True
        self.manager.status = "ENRICHING"
        res = self.manager.stop_campaign()
        self.assertTrue(res["ok"])
        self.assertTrue(self.manager.stop_requested)
        self.assertEqual(self.manager.status, "STOPPING")

    @mock.patch("services.ms4_orchestrator.services.campaign_service.SessionLocal")
    def test_start_campaign_spawns_task(self, mock_session):
        """Verifica que start_campaign cambie el estado a ejecución y retorne confirmación."""
        with mock.patch.object(self.manager, "_execute_campaign_pipeline"):
            res = self.manager.start_campaign(
                classify_with_ai=False,
                auto_harvest=False,
                is_scheduled=False,
                curator_user={"name": "Curador Test", "id": "user-123"}
            )
            self.assertTrue(res["ok"])
            self.assertTrue(self.manager.is_running)
            self.assertEqual(self.manager.trigger_type, "MANUAL")


if __name__ == "__main__":
    unittest.main()

