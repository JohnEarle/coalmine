import smtplib
from email.message import EmailMessage
from typing import Dict, Any
from .base import Notifier
from ..models import Alert
from ..logging_config import get_logger

logger = get_logger(__name__)

class EmailNotifier(Notifier):
    def send_alert(self, alert: Alert):
        if not self.config.get("enabled", True):
            return

        smtp_host = self.config.get("smtp_host")
        smtp_port = self.config.get("smtp_port", 25)
        to_addrs = self.config.get("to_addrs", [])
        from_addr = self.config.get("from_addr", "canary@localhost")
        
        if not smtp_host or not to_addrs:
            logger.error("Email notifier configured without host or recipients.")
            return

        msg = EmailMessage()
        msg.set_content(f"""
        Canary Alert Triggered!
        
        Canary: {alert.canary.name} (ID: {alert.canary.id})
        Event: {alert.event_name}
        Time: {alert.timestamp}
        Source IP: {alert.source_ip}
        User Agent: {alert.user_agent}
        External ID: {alert.external_id}
        """)

        msg['Subject'] = f"Canary Alert: {alert.event_name} on {alert.canary.name}"
        msg['From'] = from_addr
        msg['To'] = ", ".join(to_addrs)

        try:
            with smtplib.SMTP(smtp_host, smtp_port) as server:
                # Only use TLS if explicitly enabled (default: False for compatibility with test servers)
                if self.config.get("use_tls", False):
                    server.starttls()
                if self.config.get("username") and self.config.get("password"):
                    server.login(self.config["username"], self.config["password"])
                server.send_message(msg)
            logger.info(f"Email alert sent to {to_addrs}")
        except Exception as e:
            logger.error(f"Failed to send email alert: {e}")
            raise  # Re-raise for ACID retry via Celery

