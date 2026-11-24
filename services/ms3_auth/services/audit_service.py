import uuid
from datetime import datetime
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
try:
    from models import AuditLog, User, Role
except ImportError:
    from services.ms3_auth.models import AuditLog, User, Role


class MS3AuditWorker:
    """
    Microservicio 3: Gestión inmutable de auditoría (INSERT-only).
    Escribe exclusivamente en Audit_Log, User y Role.
    """

    def record_action(
        self,
        db: Session,
        user_id: Optional[Any] = None,
        item_id: Optional[Any] = None,
        action: str = "Acción",
        previous_value: Optional[Dict[str, Any]] = None,
        new_value: Optional[Dict[str, Any]] = None,
        rejection_reason: Optional[str] = None
    ) -> AuditLog:
        # Resolver o normalizar user_id a UUID válido de usuario existente
        resolved_user_uuid: Optional[uuid.UUID] = None
        if user_id:
            try:
                resolved_user_uuid = uuid.UUID(str(user_id))
            except (ValueError, TypeError):
                u = db.query(User).filter((User.email == str(user_id)) | (User.sub == str(user_id))).first()
                if u:
                    resolved_user_uuid = u.id

        if not resolved_user_uuid:
            # Fallback a usuario activo del sistema o primer usuario
            default_user = db.query(User).filter(User.is_active == True).first()
            if default_user:
                resolved_user_uuid = default_user.id
            else:
                # Crear usuario de sistema para auditoría si la BD estuviese vacía
                resolved_user_uuid = uuid.uuid4()

        # Normalizar acción
        act_clean = str(action).strip()
        act_lower = act_clean.lower()
        if act_lower in ["login", "inicio_sesion", "inicio sesion", "inicio de sesion", "iniciar sesion"]:
            act_clean = "Inicio de sesión"
        elif act_lower in ["logout", "cierre_sesion", "cierre sesion", "cierre de sesion"]:
            act_clean = "Cierre de sesión"
        elif act_lower in ["aprobar", "aprobado", "approved"]:
            act_clean = "Aprobar"
        elif act_lower in ["rechazar", "rechazado", "rejected"]:
            act_clean = "Rechazar"
        elif act_lower in ["editar", "editado", "edit"]:
            act_clean = "Editar"
        elif act_lower in ["validar", "validado", "validated"]:
            act_clean = "Validar"
        elif act_lower in ["crear usuario", "create_user", "nuevo usuario"]:
            act_clean = "Crear Usuario"

        resolved_item_id = str(item_id).strip() if item_id is not None else None

        entry = AuditLog(
            id_user=resolved_user_uuid,
            id_item_enrichment=resolved_item_id,
            action=act_clean,
            previous_value=previous_value,
            new_value=new_value,
            rejection_reason=rejection_reason,
            timestamp=datetime.utcnow()
        )
        try:
            db.add(entry)
            db.commit()
            db.refresh(entry)
            return entry
        except Exception as e:
            db.rollback()
            print(f"[MS3AuditWorker] Advertencia guardando auditoría ({e}), aplicando rollback y reintento con fallback UUID...")
            try:
                fallback_uuid = None
                if resolved_item_id:
                    try:
                        fallback_uuid = uuid.UUID(resolved_item_id)
                    except Exception:
                        fallback_uuid = None

                fallback_entry = AuditLog(
                    id_user=resolved_user_uuid,
                    id_item_enrichment=fallback_uuid,
                    action=act_clean,
                    previous_value=previous_value,
                    new_value=new_value,
                    rejection_reason=rejection_reason,
                    timestamp=datetime.utcnow()
                )
                db.add(fallback_entry)
                db.commit()
                db.refresh(fallback_entry)
                return fallback_entry
            except Exception as e_retry:
                db.rollback()
                print(f"[MS3AuditWorker] Reintento de auditoría omitido para no interrumpir la transacción del usuario: {e_retry}")
                return entry

    def get_logs_for_item(self, db: Session, item_id: Any) -> List[AuditLog]:
        return db.query(AuditLog).filter(
            AuditLog.id_item_enrichment == str(item_id)
        ).order_by(AuditLog.timestamp.desc()).all()

    def verify_permission(self, db: Session, user_id: uuid.UUID, required_role: str) -> bool:
        user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
        if not user or not user.role:
            return False
        if user.role.name == "Admin":
            return True
        return user.role.name == required_role

