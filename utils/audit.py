import logging

logger = logging.getLogger("audit")


def audit_log(user, action, target_type, target_id=None, extra=None):
    """Emit a structured audit log entry for an admin-side action.

    Use this in admin views right after the database write has succeeded
    so the log only records actions that actually took effect.

    `extra` is a free-form dict for action-specific context
    (e.g. {"old_admin_type": "...", "new_admin_type": "..."}).
    """
    actor = getattr(user, "username", None) or "anonymous"
    actor_id = getattr(user, "id", None)
    logger.info(
        "audit action=%s actor=%s actor_id=%s target=%s target_id=%s extra=%s",
        action,
        actor,
        actor_id,
        target_type,
        target_id,
        extra or {},
    )
