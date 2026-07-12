"""AgenticMail configurable self-hosted REST adapter."""
from src.infrastructure.mail.providers.configured_rest import ConfiguredRestMailAdapter

class AgenticMailAdapter(ConfiguredRestMailAdapter):
    provider_key = "agenticmail"
    display_name = "AgenticMail"
