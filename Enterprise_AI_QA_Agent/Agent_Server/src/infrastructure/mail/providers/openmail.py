"""OpenMail configurable REST adapter."""
from src.infrastructure.mail.providers.configured_rest import ConfiguredRestMailAdapter

class OpenMailAdapter(ConfiguredRestMailAdapter):
    provider_key = "openmail"
    display_name = "OpenMail"
