class BaseAlert:
    name: str | None = None

    def create_from_env(self):
        return None

    @property
    def properly_configured(self) -> bool:
        return False

    def send(self, subject: str = "", body: str = "", alert_type: str = None):
        pass
