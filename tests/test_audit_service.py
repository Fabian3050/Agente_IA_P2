import os
import sys
import unittest
from unittest import mock
import uuid
from datetime import datetime
import httpx
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SERVICES_DIR = os.path.join(PROJECT_ROOT, "services")

if SERVICES_DIR not in sys.path:
    sys.path.insert(0, SERVICES_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from common.database import Base
from services.ms3_auth.models import User, Role, AuditLog
from services.ms3_auth.services.audit_service import MS3AuditWorker
from services.ms3_auth.services.seed_service import seed_roles


class TestAuditSystem(unittest.TestCase):

    def setUp(self):
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool
        )
        TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        Role.metadata.create_all(bind=self.engine)
        self.db = TestingSessionLocal()
        seed_roles(self.db)
        self.worker = MS3AuditWorker()

        role_curador = self.db.query(Role).filter(Role.name == "Curador_VRIIC").first()
        self.user = User(
            id_role=role_curador.id,
            name="Curador",
            last_name="Auditor",
            email="curador.auditor@usach.cl",
            is_active=True
        )
        self.db.add(self.user)
        self.db.commit()

    def tearDown(self):
        self.db.close()
        Role.metadata.drop_all(bind=self.engine)

    def test_record_login_action(self):
        """Verifica que los inicios de sesión sin item_id se registren correctamente en la bitácora."""
        log = self.worker.record_action(
            db=self.db,
            user_id=self.user.id,
            item_id=None,
            action="Inicio de sesión",
            new_value={"method": "SSO USACH", "email": self.user.email}
        )
        self.assertIsNotNone(log.id)
        self.assertEqual(log.action, "Inicio de sesión")
        self.assertIsNone(log.id_item_enrichment)
        self.assertEqual(log.id_user, self.user.id)

    def test_record_user_creation_action(self):
        """Verifica el registro de creación de usuarios en la bitácora."""
        log = self.worker.record_action(
            db=self.db,
            user_id=self.user.id,
            item_id=None,
            action="Crear Usuario",
            new_value={"email": "nuevo@usach.cl", "role": "Academico"}
        )
        self.assertIsNotNone(log.id)
        self.assertEqual(log.action, "Crear Usuario")
        self.assertIn("email", log.new_value)

    def test_record_validation_and_approval_with_string_item_id(self):
        """Verifica que registros con IDs numéricos o string de la cola de enriquecimiento se almacenen."""
        log_val = self.worker.record_action(
            db=self.db,
            user_id=self.user.id,
            item_id="101",
            action="Validar",
            new_value={"titulo": "Artículo Científico", "estado": "ENRIQUECIDO"}
        )
        self.assertEqual(log_val.id_item_enrichment, "101")
        self.assertEqual(log_val.action, "Validar")

        log_app = self.worker.record_action(
            db=self.db,
            user_id=self.user.id,
            item_id="101",
            action="Aprobar",
            new_value={"titulo": "Artículo Científico", "estado": "SINCRONIZADO_DSPACE"}
        )
        self.assertEqual(log_app.id_item_enrichment, "101")
        self.assertEqual(log_app.action, "Aprobar")

        # Recuperar trazabilidad
        trail = self.worker.get_logs_for_item(self.db, "101")
        self.assertEqual(len(trail), 2)
        actions = [t.action for t in trail]
        self.assertIn("Aprobar", actions)
        self.assertIn("Validar", actions)

    @mock.patch("httpx.Client.post", side_effect=httpx.ConnectError("Connection refused"))
    @mock.patch("httpx.Client.get", side_effect=httpx.ConnectError("Connection refused"))
    def test_ms3_client_resilience(self, mock_get, mock_post):
        """Verifica que MS3Client maneje timeouts o fallos de conexión sin arrojar excepciones no controladas."""
        from services.ms4_orchestrator.clients.ms_clients import MS3Client
        client = MS3Client()
        # Llamadas sincronas cuando el servicio remoto está caído o en puerto dummy
        res = client.record_audit_sync(
            item_id="999",
            action="Aprobar",
            new_value={"titulo": "Test", "estado": "SINCRONIZADO_DSPACE"}
        )
        self.assertIsNone(res)

        activity = client.get_recent_activity_sync(limit=5)
        self.assertEqual(activity, [])

    def test_ms3_audit_api_router(self):
        """Verifica los endpoints de auditoría de MS3 vía TestClient."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from services.ms3_auth.api.audit_router import router as audit_router
        from common.database import get_db

        app = FastAPI()
        app.include_router(audit_router)

        def override_get_db():
            try:
                yield self.db
            finally:
                pass

        app.dependency_overrides[get_db] = override_get_db
        test_client = TestClient(app)

        # POST /audit/
        payload = {
            "user_id": str(self.user.id),
            "item_id": "test-uuid-1234",
            "action": "Aprobar",
            "new_value": {"titulo": "Paper Test", "estado": "SINCRONIZADO_DSPACE"}
        }
        res_post = test_client.post("/audit/", json=payload)
        self.assertEqual(res_post.status_code, 201)
        data = res_post.json()
        self.assertEqual(data["status"], "recorded")

        # GET /audit/
        res_get = test_client.get("/audit/?limit=10")
        self.assertEqual(res_get.status_code, 200)
        logs = res_get.json()
        self.assertIsInstance(logs, list)
        self.assertTrue(any(l["action"] == "Aprobar" for l in logs))

        # GET /audit/{item_id}
        res_item = test_client.get("/audit/test-uuid-1234")
        self.assertEqual(res_item.status_code, 200)
        item_logs = res_item.json()
        self.assertGreaterEqual(len(item_logs), 1)
        self.assertEqual(item_logs[0]["action"], "Aprobar")


if __name__ == "__main__":
    unittest.main()
