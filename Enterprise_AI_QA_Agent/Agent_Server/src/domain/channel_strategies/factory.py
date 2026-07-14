from __future__ import annotations

from typing import Any

from .base import ChannelStrategy
from .feishu import FeishuChannelStrategy
from .qq import QQChannelStrategy
from .weixin import WeixinChannelStrategy


class ChannelStrategyFactory:
    def __init__(self) -> None:
        self._strategies: dict[str, ChannelStrategy] = {
            "qq": QQChannelStrategy(),
            "feishu": FeishuChannelStrategy(domain="feishu"),
            "lark": FeishuChannelStrategy(domain="lark"),
            "weixin": WeixinChannelStrategy(),
        }

    def get(self, domain: str) -> ChannelStrategy:
        key = str(domain or "").strip().lower()
        try:
            return self._strategies[key]
        except KeyError as exc:
            raise ValueError(f"Unsupported communication channel domain '{domain}'.") from exc

    def definitions(self) -> dict[str, dict[str, Any]]:
        return {domain: strategy.definition.as_dict() for domain, strategy in self._strategies.items()}


channel_strategy_factory = ChannelStrategyFactory()
CHANNEL_DEFINITIONS = channel_strategy_factory.definitions()

