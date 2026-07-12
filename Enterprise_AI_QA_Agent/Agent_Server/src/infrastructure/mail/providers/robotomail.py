"""Robotomail configurable REST adapter."""
from src.infrastructure.mail.providers.configured_rest import ConfiguredRestMailAdapter

class RobotomailAdapter(ConfiguredRestMailAdapter):
    provider_key = "robotomail"
    display_name = "Robotomail"
