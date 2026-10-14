"""Purge du journal d'activité."""

from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from models.audit_log import AuditLog


def purge_old_audit_logs(db: Session, retention_days: int) -> int:
    cutoff = datetime.now() - timedelta(days=retention_days)
    deleted = db.query(AuditLog).filter(AuditLog.created_at < cutoff).delete(synchronize_session=False)
    db.commit()
    return deleted
