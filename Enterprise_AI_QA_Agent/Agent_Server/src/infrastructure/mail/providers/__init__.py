"""Concrete mail provider adapter implementations."""

from __future__ import annotations

from src.infrastructure.mail.providers.agentmail import AgentMailAdapter
from src.infrastructure.mail.providers.agenticmail import AgenticMailAdapter
from src.infrastructure.mail.providers.aliyun import AliyunMailAdapter
from src.infrastructure.mail.providers.aws_agent_mailbox import AwsAgentMailboxAdapter
from src.infrastructure.mail.providers.dead_simple_email import DeadSimpleEmailAdapter
from src.infrastructure.mail.providers.openmail import OpenMailAdapter
from src.infrastructure.mail.providers.robotomail import RobotomailAdapter
from src.infrastructure.mail.providers.smtp import SmtpMailAdapter
from src.infrastructure.mail.providers.tencent_agently import TencentAgentlyMailAdapter

__all__ = [
    "AgentMailAdapter",
    "AgenticMailAdapter",
    "AliyunMailAdapter",
    "AwsAgentMailboxAdapter",
    "DeadSimpleEmailAdapter",
    "OpenMailAdapter",
    "RobotomailAdapter",
    "SmtpMailAdapter",
    "TencentAgentlyMailAdapter",
]
