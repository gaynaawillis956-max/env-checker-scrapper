import smtplib
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr
from pathlib import Path


class SMTPSendError(Exception):
    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


class SMTPTestResult:
    """Result of SMTP credential test."""
    def __init__(self, success: bool, message: str = ""):
        self.success = success
        self.message = message


def send_email(
    host: str,
    port: int,
    user: str,
    password: str,
    to_addr: str,
    subject: str,
    html_body: str,
    from_name: str,
    smtp_timeout: int = 10,
    attachments: list = None,
) -> None:
    server = None
    try:
        server = smtplib.SMTP(host, port, timeout=smtp_timeout)
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(user, password)

        msg = MIMEMultipart("mixed")
        msg["Subject"] = subject
        msg["From"] = formataddr((from_name, user))
        msg["To"] = to_addr

        alt = MIMEMultipart("alternative")
        alt.attach(MIMEText(html_body, "html", "utf-8"))
        msg.attach(alt)

        for path in (attachments or []):
            p = Path(path)
            if not p.is_file():
                continue
            part = MIMEBase("application", "octet-stream")
            part.set_payload(p.read_bytes())
            encoders.encode_base64(part)
            part.add_header(
                "Content-Disposition",
                f'attachment; filename="{p.name}"',
            )
            msg.attach(part)

        server.sendmail(user, [to_addr], msg.as_string())

    except smtplib.SMTPAuthenticationError:
        raise SMTPSendError("auth_failed")
    except smtplib.SMTPServerDisconnected:
        raise SMTPSendError("disconnected")
    except smtplib.SMTPConnectError:
        raise SMTPSendError("connect_failed")
    except smtplib.SMTPRecipientsRefused:
        raise SMTPSendError("recipient_refused")
    except smtplib.SMTPException as e:
        raise SMTPSendError(f"smtp_error: {e}")
    except (OSError, ValueError) as e:
        raise SMTPSendError(f"network_error: {e}")
    except Exception as e:
        raise SMTPSendError(f"unexpected: {e}")
    finally:
        if server is not None:
            try:
                server.quit()
            except Exception:
                pass


def test_smtp(
    host: str,
    port: int,
    user: str,
    password: str,
    smtp_timeout: int = 10,
) -> SMTPTestResult:
    """Test SMTP credential validity without sending an email."""
    server = None
    try:
        server = smtplib.SMTP(host, port, timeout=smtp_timeout)
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(user, password)
        return SMTPTestResult(success=True, message="Connected and authenticated successfully")

    except smtplib.SMTPAuthenticationError as e:
        return SMTPTestResult(success=False, message="Authentication failed: invalid credentials")
    except smtplib.SMTPServerDisconnected as e:
        return SMTPTestResult(success=False, message="Server disconnected unexpectedly")
    except smtplib.SMTPConnectError as e:
        return SMTPTestResult(success=False, message=f"Connection failed: {e}")
    except smtplib.SMTPException as e:
        return SMTPTestResult(success=False, message=f"SMTP error: {e}")
    except (OSError, ValueError) as e:
        return SMTPTestResult(success=False, message=f"Network error: {e}")
    except Exception as e:
        return SMTPTestResult(success=False, message=f"Unexpected error: {e}")
    finally:
        if server is not None:
            try:
                server.quit()
            except Exception:
                pass
