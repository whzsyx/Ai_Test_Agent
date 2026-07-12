"""Dead Simple Email configurable REST adapter."""
from src.infrastructure.mail.providers.configured_rest import ConfiguredRestMailAdapter

class DeadSimpleEmailAdapter(ConfiguredRestMailAdapter):
    provider_key = "dead_simple_email"
    display_name = "Dead Simple Email"
