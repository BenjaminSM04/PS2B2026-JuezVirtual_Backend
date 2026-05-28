import logging
import dramatiq

from options.options import SysOptions
from utils.shortcuts import send_email, DRAMATIQ_WORKER_ARGS

logger = logging.getLogger(__name__)


def _do_send_email(from_name, to_email, to_name, subject, content):
    smtp_config = SysOptions.smtp_config
    if not smtp_config:
        logger.warning(
            "send_email skipped: SysOptions.smtp_config is empty. "
            "Configure SMTP in /admin/conf before any email-dependent flow."
        )
        raise RuntimeError("SMTP is not configured")
    send_email(smtp_config=smtp_config,
               from_name=from_name,
               to_email=to_email,
               to_name=to_name,
               subject=subject,
               content=content)
    logger.info("Email sent to %s (subject=%r)", to_email, subject)


def send_email_sync(from_name, to_email, to_name, subject, content):
    """Synchronous fallback. Re-raises errors so the caller can surface them."""
    _do_send_email(from_name, to_email, to_name, subject, content)


@dramatiq.actor(**DRAMATIQ_WORKER_ARGS(max_retries=3))
def send_email_async(from_name, to_email, to_name, subject, content):
    try:
        _do_send_email(from_name, to_email, to_name, subject, content)
    except Exception as e:
        logger.exception("send_email_async failed for %s: %s", to_email, e)
        raise
