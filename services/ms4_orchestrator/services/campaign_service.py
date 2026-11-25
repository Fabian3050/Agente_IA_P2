import asyncio
import logging
import os
import threading
from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session

try:
    from common.database import SessionLocal
    from models import DSpaceEnrichmentQueue
    from clients.ms_clients import MS3Client
    from services.dspace_service import DSpaceService
    from services.enrichment_service import EnrichmentService
except ImportError:
    from services.common.database import SessionLocal
    from services.ms4_orchestrator.models import DSpaceEnrichmentQueue
    from services.ms4_orchestrator.clients.ms_clients import MS3Client
    from services.ms4_orchestrator.services.dspace_service import DSpaceService
    from services.ms4_orchestrator.services.enrichment_service import EnrichmentService

logger = logging.getLogger("campaign_service")

# Configuración de calendario anual
ANNUAL_CAMPAIGN_ENABLED = os.getenv("ANNUAL_CAMPAIGN_ENABLED", "true").lower() in ("true", "1", "yes")
ANNUAL_CAMPAIGN_MONTH = int(os.getenv("ANNUAL_CAMPAIGN_MONTH", "4"))         # 4 = Abril
ANNUAL_CAMPAIGN_DAY = int(os.getenv("ANNUAL_CAMPAIGN_DAY", "15"))            # 15 de Abril
ANNUAL_CAMPAIGN_HOUR = int(os.getenv("ANNUAL_CAMPAIGN_HOUR", "2"))           # 02:00 AM
ANNUAL_CAMPAIGN_CHECK_INTERVAL_SECONDS = int(os.getenv("ANNUAL_CAMPAIGN_CHECK_INTERVAL_SECONDS", "3600"))


def compute_next_scheduled_run() -> datetime:
    """Calcula la próxima fecha de ejecución programada en base al calendario anual."""
    now = datetime.now()
    target_year = now.year
    target_date = datetime(target_year, ANNUAL_CAMPAIGN_MONTH, ANNUAL_CAMPAIGN_DAY, ANNUAL_CAMPAIGN_HOUR, 0, 0)
    if now >= target_date:
        target_year += 1
        target_date = datetime(target_year, ANNUAL_CAMPAIGN_MONTH, ANNUAL_CAMPAIGN_DAY, ANNUAL_CAMPAIGN_HOUR, 0, 0)
    return target_date


class AnnualCampaignManager:
    """
    Gestor de la Campaña Anual y Enriquecimiento Autónomo / Manual de publicaciones.
    Garantiza la ejecución en segundo plano sin bloquear el servidor web.
    """

    def __init__(self):
        self.is_running: bool = False
        self.status: str = "IDLE"  # IDLE, SCANNING, ENRICHING, STOPPING, STOPPED, COMPLETED, ERROR
        self.trigger_type: str = "MANUAL"  # SCHEDULED, MANUAL
        self.curator_user: Optional[Dict[str, Any]] = None
        self.total_items: int = 0
        self.processed_items: int = 0
        self.success_count: int = 0
        self.failed_count: int = 0
        self.started_at: Optional[str] = None
        self.completed_at: Optional[str] = None
        self.current_item_title: Optional[str] = None
        self.current_step: str = "Inactivo. Sistema en espera del calendario o ejecución manual."
        self.last_run_year: Optional[int] = None
        self.last_error: Optional[str] = None
        self.stop_requested: bool = False
        self._background_task: Optional[asyncio.Task] = None
        self.main_loop: Optional[asyncio.AbstractEventLoop] = None

    def set_main_loop(self, loop: asyncio.AbstractEventLoop):
        """Registra el event loop principal de FastAPI para programar corrutinas."""
        self.main_loop = loop

    def get_status(self) -> Dict[str, Any]:
        """Retorna el estado detallado de la campaña y métricas en tiempo real."""
        next_run = compute_next_scheduled_run()
        progress_pct = 0
        if self.total_items > 0:
            progress_pct = round((self.processed_items / self.total_items) * 100, 1)

        return {
            "is_running": self.is_running,
            "status": self.status,
            "trigger_type": self.trigger_type,
            "total_items": self.total_items,
            "processed_items": self.processed_items,
            "success_count": self.success_count,
            "failed_count": self.failed_count,
            "progress_percent": progress_pct,
            "current_step": self.current_step,
            "current_item_title": self.current_item_title,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "last_run_year": self.last_run_year,
            "last_error": self.last_error,
            "next_scheduled_run": next_run.isoformat(),
            "next_scheduled_run_formatted": next_run.strftime("%d/%m/%Y a las %H:%M hrs"),
            "schedule_config": {
                "enabled": ANNUAL_CAMPAIGN_ENABLED,
                "month": ANNUAL_CAMPAIGN_MONTH,
                "day": ANNUAL_CAMPAIGN_DAY,
                "hour": ANNUAL_CAMPAIGN_HOUR
            }
        }

    def start_campaign(
        self,
        classify_with_ai: bool = True,
        auto_harvest: bool = False,
        batch_size: int = 10,
        is_scheduled: bool = False,
        curator_user: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Inicia la campaña de enriquecimiento en segundo plano."""
        if self.is_running:
            return {
                "ok": False,
                "message": "La campaña de enriquecimiento ya se encuentra en ejecución.",
                "status": self.get_status()
            }

        self.is_running = True
        self.status = "SCANNING" if auto_harvest else "ENRICHING"
        self.trigger_type = "SCHEDULED" if is_scheduled else "MANUAL"
        self.curator_user = curator_user
        self.total_items = 0
        self.processed_items = 0
        self.success_count = 0
        self.failed_count = 0
        self.started_at = datetime.utcnow().isoformat()
        self.completed_at = None
        self.current_item_title = None
        self.current_step = "Iniciando campaña de enriquecimiento..."
        self.last_error = None
        self.stop_requested = False

        print(f"[CampaignManager] Campaña iniciada ({self.trigger_type}) por {curator_user.get('name') if curator_user else 'Sistema'}", flush=True)

        # Determinar el loop activo para programar la corrutina
        loop = None
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            if self.main_loop and self.main_loop.is_running():
                loop = self.main_loop

        if loop and loop.is_running():
            self._background_task = loop.create_task(
                self._execute_campaign_pipeline(
                    classify_with_ai=classify_with_ai,
                    auto_harvest=auto_harvest,
                    batch_size=batch_size,
                    is_scheduled=is_scheduled
                )
            )
        else:
            # Fallback seguro: hilo dedicado con su propio loop
            def run_in_dedicated_thread():
                new_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(new_loop)
                new_loop.run_until_complete(
                    self._execute_campaign_pipeline(
                        classify_with_ai=classify_with_ai,
                        auto_harvest=auto_harvest,
                        batch_size=batch_size,
                        is_scheduled=is_scheduled
                    )
                )
                new_loop.close()

            t = threading.Thread(target=run_in_dedicated_thread, daemon=True, name="AnnualCampaignWorker")
            t.start()

        return {
            "ok": True,
            "message": "Campaña de enriquecimiento iniciada exitosamente en segundo plano.",
            "status": self.get_status()
        }

    def stop_campaign(self) -> Dict[str, Any]:
        """Solicita la detención elegante de la campaña en curso."""
        if not self.is_running:
            return {
                "ok": False,
                "message": "No hay ninguna campaña en ejecución en este momento.",
                "status": self.get_status()
            }

        self.stop_requested = True
        self.status = "STOPPING"
        self.current_step = "Detención solicitada. Concluyendo el registro actual..."
        print("[CampaignManager] Solicitud de detención recibida.", flush=True)
        return {
            "ok": True,
            "message": "Detención solicitada. La campaña finalizará al concluir el ítem en proceso.",
            "status": self.get_status()
        }

    def reset_state(self) -> Dict[str, Any]:
        """Fuerza el reinicio del estado de la campaña en memoria a Inactivo (IDLE)."""
        self.is_running = False
        self.stop_requested = False
        self.status = "IDLE"
        self.current_step = "Estado de campaña reiniciado a Inactivo."
        self.current_item_title = None
        print("[CampaignManager] Estado reiniciado forzosamente a IDLE.", flush=True)
        return {"ok": True, "message": "Estado de la campaña reiniciado.", "status": self.get_status()}

    async def _execute_campaign_pipeline(
        self,
        classify_with_ai: bool = True,
        auto_harvest: bool = False,
        batch_size: int = 10,
        is_scheduled: bool = False
    ):
        """Ejecuta el pipeline completo: escaneo opcional si cola vacía, enriquecimiento y auditoría."""
        db: Session = SessionLocal()
        enrichment_service = EnrichmentService()
        dspace_service = DSpaceService()
        ms3_client = MS3Client()

        try:
            print("[CampaignManager] Iniciando pipeline de campaña...", flush=True)

            # 1. Escaneo inicial de DSpace-CRIS SOLO si auto_harvest está habilitado y la cola está vacía
            if auto_harvest:
                pending_count = (
                    db.query(DSpaceEnrichmentQueue)
                    .filter(DSpaceEnrichmentQueue.estado == "PENDIENTE")
                    .count()
                )
                if pending_count == 0:
                    self.current_step = "Cola vacía. Escaneando DSpace-CRIS para detectar publicaciones incompletas..."
                    print(f"[CampaignManager] {self.current_step}", flush=True)
                    try:
                        await dspace_service.count_missing(save_to_db=True, use_cache=True, db=db)
                    except Exception as e_scan:
                        logger.warning(f"[CampaignManager] Advertencia en escaneo inicial de DSpace: {e_scan}")
                        print(f"[CampaignManager] Advertencia en escaneo inicial: {e_scan}", flush=True)
                else:
                    self.current_step = f"Cola detectada con {pending_count} registros pendientes. Iniciando enriquecimiento directo..."
                    print(f"[CampaignManager] {self.current_step}", flush=True)

            if self.stop_requested:
                self.status = "STOPPED"
                self.current_step = "Campaña detenida a solicitud del usuario."
                return

            # 2. Consultar registros PENDIENTES en la cola
            self.status = "ENRICHING"
            self.current_step = "Consultando registros pendientes en la cola..."

            pending_items = (
                db.query(DSpaceEnrichmentQueue)
                .filter(DSpaceEnrichmentQueue.estado == "PENDIENTE")
                .order_by(DSpaceEnrichmentQueue.id.asc())
                .all()
            )

            self.total_items = len(pending_items)
            self.current_step = f"Enriqueciendo {self.total_items} publicaciones pendientes..."
            print(f"[CampaignManager] Total de publicaciones a procesar: {self.total_items}", flush=True)

            if self.total_items == 0:
                self.current_step = "No se encontraron publicaciones en estado PENDIENTE en la cola."
                self.status = "COMPLETED"
                print(f"[CampaignManager] {self.current_step}", flush=True)
                return

            for it in pending_items:
                if self.stop_requested:
                    self.status = "STOPPED"
                    self.current_step = f"Campaña detenida por el usuario tras procesar {self.processed_items}/{self.total_items} publicaciones."
                    print(f"[CampaignManager] {self.current_step}", flush=True)
                    break

                self.current_item_title = it.titulo or f"Publicación #{it.id}"
                print(f"[CampaignManager] [{self.processed_items + 1}/{self.total_items}] Procesando #{it.id} ({self.current_item_title[:60]})...", flush=True)

                try:
                    res = await enrichment_service.enrich_item(it, db, classify_with_ai=classify_with_ai)
                    st = res.get("estado") if isinstance(res, dict) else "ENRIQUECIDO"
                    if st in ["ENRIQUECIDO", "COMPLETO", "PENDIENTE_VALIDACION", "CLASIFICADO_LLM", "ENRIQUECIDO_FUENTES"]:
                        self.success_count += 1
                    else:
                        self.failed_count += 1
                except Exception as e_item:
                    logger.warning(f"[CampaignManager] Error enriqueciendo publicación #{it.id}: {e_item}")
                    print(f"[CampaignManager] Error en publicación #{it.id}: {e_item}", flush=True)
                    self.failed_count += 1

                self.processed_items += 1
                await asyncio.sleep(0.1)

            if not self.stop_requested:
                self.status = "COMPLETED"
                self.current_step = f"Campaña concluida: {self.processed_items} publicaciones procesadas ({self.success_count} exitosas, {self.failed_count} con alertas)."
                self.last_run_year = datetime.now().year
                print(f"[CampaignManager] {self.current_step}", flush=True)

            self.completed_at = datetime.utcnow().isoformat()

            # 3. Registrar auditoría institucional inmutable en MS3
            try:
                action_name = "Campaña Anual Programada" if is_scheduled else "Campaña Anual Manual"
                user_id = self.curator_user.get("id") if self.curator_user else None
                user_name = self.curator_user.get("name") if self.curator_user else ("Sistema / Agente Autónomo" if is_scheduled else "Curador VRIIC")
                ms3_client.record_audit_sync(
                    action=action_name,
                    user_id=user_id,
                    new_value={
                        "total_procesados": self.processed_items,
                        "total_objetivo": self.total_items,
                        "exitosos": self.success_count,
                        "fallidos": self.failed_count,
                        "tipo": "Programada (Abril)" if is_scheduled else "Manual a demanda",
                        "resumen": f"{action_name} ejecutada por {user_name}: {self.processed_items} publicaciones procesadas ({self.success_count} enriquecidas exitosamente)."
                    }
                )
            except Exception as e_aud:
                logger.warning(f"[CampaignManager] Error registrando auditoría en MS3: {e_aud}")

        except Exception as e:
            self.status = "ERROR"
            self.last_error = str(e)
            self.current_step = f"Error en la ejecución de la campaña: {e}"
            logger.error(f"[CampaignManager] Error crítico en campaña: {e}")
            print(f"[CampaignManager] Error crítico: {e}", flush=True)
        finally:
            self.is_running = False
            self.stop_requested = False
            db.close()

    async def scheduler_worker_loop(self):
        """
        Bucle en segundo plano que vigila el calendario.
        Verifica periódicamente si llegó el mes, día y hora programados (ej. 15 de abril a las 02:00 AM)
        y activa la campaña autónoma si no se ha ejecutado ese año.
        """
        logger.info(f"[CampaignScheduler] Vigilancia activa. Próxima fecha objetivo: Mes {ANNUAL_CAMPAIGN_MONTH}, Día {ANNUAL_CAMPAIGN_DAY}, {ANNUAL_CAMPAIGN_HOUR:02d}:00 hrs.")
        while True:
            try:
                await asyncio.sleep(ANNUAL_CAMPAIGN_CHECK_INTERVAL_SECONDS)
                if not ANNUAL_CAMPAIGN_ENABLED:
                    continue

                now = datetime.now()
                is_target_time = (
                    now.month == ANNUAL_CAMPAIGN_MONTH and
                    now.day == ANNUAL_CAMPAIGN_DAY and
                    now.hour == ANNUAL_CAMPAIGN_HOUR
                )

                if is_target_time and self.last_run_year != now.year and not self.is_running:
                    logger.info("[CampaignScheduler] ¡Fecha anual alcanzada! Iniciando Campaña Anual Programada autónomamente...")
                    self.start_campaign(
                        classify_with_ai=True,
                        auto_harvest=True,
                        batch_size=10,
                        is_scheduled=True,
                        curator_user={"name": "Sistema / Agente Autónomo", "id": None}
                    )
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"[CampaignScheduler] Advertencia en ciclo de scheduler: {e}")


# Instancia singleton para compartir entre el router de FastAPI y el ciclo de vida del microservicio
campaign_manager = AnnualCampaignManager()
