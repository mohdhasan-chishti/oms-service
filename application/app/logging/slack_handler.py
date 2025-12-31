import os
import logging
import requests
from datetime import datetime, timezone
class SlackErrorHandler(logging.Handler):
    """Sends ERROR and CRITICAL logs to Slack"""
    def __init__(self):
        super().__init__(level=logging.ERROR)
        self.webhook = os.getenv('SLACK_WEBHOOK_URL')
        self.enabled = self.webhook and os.getenv('APPLICATION_ENVIRONMENT', '').lower() == 'local'
        
    def emit(self, record):
        if not self.enabled:
            return
        try:
            # Context fields
            env = os.getenv('APPLICATION_ENVIRONMENT', 'LOCAL').upper()
            service = 'rozana-oms'
            ts = datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat()
            logger_name = record.name
            module = getattr(record, 'module', '')
            func = getattr(record, 'funcName', '')
            line = getattr(record, 'lineno', '')


            # Build formatted Slack message similar to template
            lines = []
            lines.append("Alerting Notification action")
            lines.append("")
            lines.append(f":mag: Monitor {env}-MONITOR Please investigate the issue.")
            lines.append("")
            lines.append("Error Details")
            lines.append(f"- :clock1: Timestamp: {ts}")
            lines.append(f"- :triangular_flag_on_post: Level: **{record.levelname}**")
            lines.append(f"- :warning: Logger: {logger_name}")
            lines.append(f"- :satellite: Service: {service}")
            lines.append(f"- :globe_with_meridians: Environment: {env}")
            lines.append(f"- :file_folder: Module: {module}")
            lines.append(f"- :pushpin: Function: {func}")
            lines.append(f"- :straight_ruler: Line Number: {line}")
            lines.append(f"- :memo: Message:")
            lines.append("")
            # Message body in a code block for readability
            lines.append("```" + str(record.getMessage()) + "```")

            text = "\n".join(lines)
            requests.post(self.webhook, json={"text": text}, timeout=2)
        except:
            pass


# Export a singleton handler instance for reuse
slack_handler = SlackErrorHandler()
