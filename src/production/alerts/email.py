from __future__ import annotations

from email.message import EmailMessage
import smtplib

from ..models import ProductionAlert


class EmailAlertSink:
    name = "email"

    def __init__(
        self,
        smtp_host: str,
        smtp_port: int,
        username: str | None,
        password: str | None,
        from_address: str,
        to_addresses: list[str],
        use_tls: bool = True,
    ) -> None:
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.username = username
        self.password = password
        self.from_address = from_address
        self.to_addresses = to_addresses
        self.use_tls = use_tls

    def send(self, alert: ProductionAlert) -> dict:
        message = EmailMessage()
        message["Subject"] = f"[Wolf Model][{alert.severity}] {alert.title}"
        message["From"] = self.from_address
        message["To"] = ", ".join(self.to_addresses)
        message.set_content(
            "\n".join(
                [
                    f"Severity: {alert.severity}",
                    f"Component: {alert.component}",
                    f"Run ID: {alert.production_run_id}",
                    "",
                    alert.message,
                ]
            )
        )
        try:
            with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=30) as client:
                if self.use_tls:
                    client.starttls()
                if self.username:
                    client.login(self.username, self.password or "")
                client.send_message(message)
            return {"channel": self.name, "success": True, "error": None}
        except Exception as error:
            return {"channel": self.name, "success": False, "error": type(error).__name__}
