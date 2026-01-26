from typing import List, Dict, Type
from .base import Notifier
from .email import EmailNotifier
from .webhook import WebhookNotifier
from .syslog import SyslogNotifier
from ..config_loader import get_alert_outputs

class NotificationRegistry:
    _mapping = {
        "email": EmailNotifier,
        "webhook": WebhookNotifier,
        "syslog": SyslogNotifier
    }

    @classmethod
    def get_notifiers(cls) -> List[Notifier]:
        """
        Instantiate all configured and enabled notifiers.
        """
        configs = get_alert_outputs()
        notifiers = []
        
        for name, conf in configs.items():
            if not conf.get("enabled", True):
                continue
                
            n_type = conf.get("type")
            notifier_cls = cls._mapping.get(n_type)
            
            if notifier_cls:
                notifiers.append(notifier_cls(conf))
        
        return notifiers
