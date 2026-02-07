import logging
import logging.handlers
import socket
from typing import Dict, Any
from .base import Notifier
from ..models import Alert
from ..logging_config import get_logger

logger = get_logger(__name__)

class SyslogNotifier(Notifier):
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self._syslog_logger = None
        self._setup_logger()

    def _setup_logger(self):
        """
        Configure a specific logger for syslog injection.
        """
        host = self.config.get("host", "localhost")
        port = self.config.get("port", 514)
        protocol = self.config.get("protocol", "UDP").upper()
        facility = self.config.get("facility", "local7")
        
        address = (host, port)
        
        # Determine socket type
        socktype = socket.SOCK_DGRAM if protocol == "UDP" else socket.SOCK_STREAM
        
        try:
            handler = logging.handlers.SysLogHandler(address=address, facility=facility, socktype=socktype)
            
            # Simple formatter
            formatter = logging.Formatter('%(name)s: %(message)s')
            handler.setFormatter(formatter)
            
            self._syslog_logger = logging.getLogger(f"syslog_notifier_{host}_{port}")
            self._syslog_logger.setLevel(logging.INFO)
            self._syslog_logger.addHandler(handler)
            self._syslog_logger.propagate = False # Do not propagate to root logger (app logs)
            
        except Exception as e:
            logger.error(f"Failed to initialize Syslog handler: {e}")

    def send_alert(self, alert: Alert):
        if not self.config.get("enabled", True):
            return

        if not self._syslog_logger:
            self._setup_logger()
            if not self._syslog_logger:
                return

        # KV-formatted syslog message
        msg = (
            f"CANARY_ALERT "
            f"canary_name=\"{alert.canary.name}\" "
            f"canary_id=\"{alert.canary.id}\" "
            f"event=\"{alert.event_name}\" "
            f"src_ip=\"{alert.source_ip}\" "
            f"ua=\"{alert.user_agent}\" "
            f"ext_id=\"{alert.external_id}\""
        )

        try:
            self._syslog_logger.info(msg)
            logger.info(f"Syslog alert sent to {self.config.get('host')}:{self.config.get('port')}")
        except Exception as e:
            logger.error(f"Failed to send syslog alert: {e}")
