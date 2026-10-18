from services import notify


class FakeSMTP:
    sent: list = []

    def __init__(self, host, port, timeout=None):
        self.host, self.port, self.calls = host, port, []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def starttls(self):
        self.calls.append("starttls")

    def login(self, user, password):
        self.calls.append(("login", user, password))

    def sendmail(self, sender, recipients, text):
        FakeSMTP.sent.append({"host": self.host, "port": self.port, "sender": sender,
                              "recipients": recipients, "calls": self.calls, "text": text})


def test_email_channel_configured_from_interface(api, monkeypatch):
    monkeypatch.setattr(notify.smtplib, "SMTP", FakeSMTP)
    FakeSMTP.sent = []
    try:
        # Activer sans serveur ni destinataire : refusé ; adresse invalide : refusée
        api.put("/notification-settings/", {"email_enabled": True}, code=422)
        api.put("/notification-settings/", {"email_to": "pas-une-adresse"}, code=422)

        conf = api.put("/notification-settings/", {
            "email_enabled": True, "smtp_host": "smtp.example.org", "smtp_port": 587, "smtp_security": "starttls",
            "smtp_user": "aquas@example.org", "smtp_password": "s3cr3t-smtp", "email_to": "moi@example.org, toi@example.org",
        })
        assert conf["email_enabled"] and conf["smtp_password_set"] and "smtp_password" not in conf

        result = api.post("/notification-settings/test", {"channel": "email"})
        assert result["results"] == {"email": None}
        mail = FakeSMTP.sent[-1]
        assert mail["recipients"] == ["moi@example.org", "toi@example.org"]
        assert mail["sender"] == "aquas@example.org"
        assert mail["calls"] == ["starttls", ("login", "aquas@example.org", "s3cr3t-smtp")]

        # Les alertes partent aussi par e-mail
        notify.dispatch_alert("[AquasManager] Test", "Température haute")
        assert len(FakeSMTP.sent) == 2
    finally:
        api.put("/notification-settings/", {"email_enabled": False, "smtp_password": ""})


def test_email_error_hides_password(api, monkeypatch):
    class Failing(FakeSMTP):
        def login(self, user, password):
            raise RuntimeError(f"auth refusée pour {password}")

    monkeypatch.setattr(notify.smtplib, "SMTP", Failing)
    try:
        api.put("/notification-settings/", {"email_enabled": True, "smtp_host": "smtp.example.org",
                                            "smtp_user": "u", "smtp_password": "motdepasse-123",
                                            "email_to": "moi@example.org"})
        error = api.post("/notification-settings/test", {"channel": "email"})["results"]["email"]
        assert error and "motdepasse-123" not in error
    finally:
        api.put("/notification-settings/", {"email_enabled": False, "smtp_password": ""})
