"""最小 astrbot.api.message_components 桩。"""

from __future__ import annotations

from typing import Any


class BaseMessageComponent:
    def __init__(self, **kwargs):
        self.data: dict[str, Any] = kwargs
        for k, v in kwargs.items():
            setattr(self, k, v)
        self.type: str = self.__class__.__name__.lower()


class Plain(BaseMessageComponent):
    def __init__(self, text: str = ""):
        super().__init__(text=text)


class At(BaseMessageComponent):
    def __init__(self, qq: str = ""):
        super().__init__(qq=qq)


class Image(BaseMessageComponent):
    @staticmethod
    def fromURL(url: str) -> "Image":
        return Image(url=url)

    @staticmethod
    def fromFileSystem(path: str) -> "Image":
        return Image(file=path)


class File(BaseMessageComponent):
    def __init__(self, file: str = "", name: str = ""):
        super().__init__(file=file, name=name)


class Record(BaseMessageComponent):
    pass


class Video(BaseMessageComponent):
    @staticmethod
    def fromFileSystem(path: str = "") -> "Video":
        return Video(file=path)

    @staticmethod
    def fromURL(url: str = "") -> "Video":
        return Video(url=url)


class Node(BaseMessageComponent):
    pass


class Nodes(BaseMessageComponent):
    pass


class Poke(BaseMessageComponent):
    pass
