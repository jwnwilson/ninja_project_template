"""
Celery tasks for the {{project_slug}} application.
"""

import logging

from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger(__name__)


@shared_task
def send_email_task(
    subject, message, recipient_list, from_email=None, fail_silently=False
):
    """Send notification email asynchronously."""
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=from_email or settings.DEFAULT_FROM_EMAIL,
            recipient_list=recipient_list,
            fail_silently=fail_silently,
        )
        logger.info(f"Email sent successfully to {', '.join(recipient_list)}")
    except Exception as e:
        logger.exception(f"Failed to send email: {str(e)}")
        raise
