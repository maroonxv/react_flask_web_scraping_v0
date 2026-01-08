from abc import ABC, abstractmethod
from ..value_objects.binary_response import BinaryResponse


class IBinaryHttpClient(ABC):
    """二进制 HTTP 客户端接口"""

    @abstractmethod
    def get_binary(self, url: str, timeout: int = 30) -> BinaryResponse:
        """
        下载二进制内容

        参数:
            url: 目标 URL
            timeout: 超时时间（秒）

        返回:
            BinaryResponse 值对象
        """
        pass
