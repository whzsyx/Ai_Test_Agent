"""AWS Agent Mailbox configurable HTTP adapter."""
from src.infrastructure.mail.providers.configured_rest import ConfiguredRestMailAdapter

class AwsAgentMailboxAdapter(ConfiguredRestMailAdapter):
    provider_key = "aws_agent_mailbox"
    display_name = "AWS Agent Mailbox"
