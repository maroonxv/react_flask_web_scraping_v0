"""
PDF 异常类模块

定义 PDF 内容提取过程中可能发生的异常类型。
"""


class PdfExtractionError(Exception):
    """
    PDF 提取错误异常
    
    当 PDF 文件损坏、格式无效或解析失败时抛出此异常。
    
    Attributes:
        message: 错误描述信息
    """
    
    def __init__(self, message: str = "Failed to extract PDF content"):
        self.message = message
        super().__init__(self.message)


class PdfPasswordProtectedError(Exception):
    """
    PDF 受密码保护错误异常
    
    当尝试提取受密码保护的 PDF 文件内容时抛出此异常。
    
    Attributes:
        message: 错误描述信息
    """
    
    def __init__(self, message: str = "PDF is password protected"):
        self.message = message
        super().__init__(self.message)
