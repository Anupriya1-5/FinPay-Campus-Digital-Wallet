from app.models.models import AuditLog, Notification

def audit(db, actor, action, entity_type, entity_id, details=""):
    db.add(AuditLog(actor_user_id=actor.id if actor else None, action=action,
                    entity_type=entity_type, entity_id=str(entity_id), details=details[:700]))

def notify(db, user_id, title, message):
    db.add(Notification(user_id=user_id, title=title, message=message[:500]))
