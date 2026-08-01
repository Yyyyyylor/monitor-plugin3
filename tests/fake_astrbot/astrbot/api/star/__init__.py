"""最小 astrbot.api.star 桩 — Context / Star。"""

from __future__ import annotations

from typing import Any


class Context:
    """插件上下文最小桩。"""

    def __init__(self):
        self._stars: list = []

    def get_all_stars(self) -> list:
        return self._stars

    async def send_message(self, session: str, message_chain) -> bool:
        return True


class Star:
    """Star 基类最小桩。"""

    def __init__(self, context: Context):
        self.context = context

    async def html_render(
        self,
        tmpl: str,
        data: dict,
        return_url: bool = True,
        options: dict | None = None,
    ) -> str:
        return "file:///tmp/fake_render.png"

    async def text_to_image(self, text: str, return_url: bool = True) -> str:
        return "file:///tmp/fake_t2i.png"

    async def terminate(self) -> None:
        pass
