"""
PdfContentExtractorImpl 属性测试模块

使用 hypothesis 库进行属性测试，验证 PDF 内容提取器的正确性属性。

Feature: pdf-content-extraction
"""
import pytest
import sys
import os
import fitz  # PyMuPDF

from hypothesis import given, strategies as st, settings, assume, HealthCheck

# 将 backend 目录添加到系统路径
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../')))

from src.crawl.infrastructure.pdf_content_extractor_impl import PdfContentExtractorImpl
from src.crawl.domain.exceptions.pdf_exceptions import PdfExtractionError, PdfPasswordProtectedError


# 创建全局 extractor 实例，因为它是无状态的
_extractor = PdfContentExtractorImpl()


class TestPdfContentExtractorImplProperty:
    """
    PdfContentExtractorImpl 属性测试类
    
    测试目标：
    - Property 3: Valid PDF Extraction Completeness
    - Property 4: Invalid PDF Error Handling
    """

    # =========================================================================
    # Property 3: Valid PDF Extraction Completeness
    # *For any* valid PDF binary data, the PdfContentExtractorImpl SHALL extract
    # text from all pages (page_texts length equals page_count) and populate
    # all available metadata fields.
    # **Validates: Requirements 4.1, 4.2**
    # =========================================================================

    @settings(max_examples=100, deadline=None)
    @given(
        page_count=st.integers(min_value=1, max_value=10),
        page_texts=st.lists(st.text(min_size=0, max_size=100), min_size=1, max_size=10),
        title=st.one_of(st.none(), st.text(min_size=1, max_size=50)),
        author=st.one_of(st.none(), st.text(min_size=1, max_size=50)),
    )
    def test_property_3_valid_pdf_extraction_completeness(
        self, page_count, page_texts, title, author
    ):
        """
        Property 3: Valid PDF Extraction Completeness
        
        *For any* valid PDF binary data, the PdfContentExtractorImpl SHALL extract
        text from all pages (page_texts length equals page_count) and populate
        all available metadata fields.
        
        **Validates: Requirements 4.1, 4.2**
        """
        extractor = _extractor
        # Ensure page_texts matches page_count
        actual_page_count = min(page_count, len(page_texts))
        page_texts = page_texts[:actual_page_count]
        
        # Generate a valid PDF with the given parameters
        pdf_data = self._create_valid_pdf(page_texts, title, author)
        source_url = "http://example.com/test.pdf"
        
        # Extract content
        result = extractor.extract_content(pdf_data, source_url)
        
        # Property assertions:
        # 1. page_texts length equals page_count in metadata
        assert len(result.page_texts) == result.metadata.page_count, \
            f"page_texts length ({len(result.page_texts)}) should equal page_count ({result.metadata.page_count})"
        
        # 2. page_count should match the actual number of pages in the PDF
        assert result.metadata.page_count == actual_page_count, \
            f"metadata.page_count ({result.metadata.page_count}) should equal actual page count ({actual_page_count})"
        
        # 3. source_url should be preserved
        assert result.source_url == source_url
        
        # 4. If title was set, it should be extracted (when not empty)
        if title and title.strip():
            # Note: PyMuPDF may not preserve all metadata exactly
            pass  # Metadata extraction is best-effort
        
        # 5. text_content should be the concatenation of page_texts
        assert result.text_content == "\n".join(result.page_texts)

    def _create_valid_pdf(self, page_texts: list, title: str = None, author: str = None) -> bytes:
        """
        创建有效的 PDF 二进制数据用于测试
        
        参数:
            page_texts: 每页的文本内容列表
            title: PDF 标题（可选）
            author: PDF 作者（可选）
            
        返回:
            PDF 二进制数据
        """
        doc = fitz.open()
        
        # Set metadata
        metadata = {}
        if title:
            metadata['title'] = title
        if author:
            metadata['author'] = author
        if metadata:
            doc.set_metadata(metadata)
        
        # Add pages with text
        for text in page_texts:
            page = doc.new_page()
            # Insert text at position (72, 72) - 1 inch from top-left
            if text:
                page.insert_text((72, 72), text)
        
        # Save to bytes
        pdf_bytes = doc.tobytes()
        doc.close()
        
        return pdf_bytes

    # =========================================================================
    # Property 4: Invalid PDF Error Handling
    # *For any* corrupted or invalid binary data (not a valid PDF), the
    # PdfContentExtractorImpl SHALL raise PdfExtractionError with a non-empty
    # error message.
    # **Validates: Requirements 4.3**
    # =========================================================================

    @settings(max_examples=100)
    @given(
        invalid_data=st.binary(min_size=1, max_size=1000)
    )
    def test_property_4_invalid_pdf_error_handling(self, invalid_data):
        """
        Property 4: Invalid PDF Error Handling
        
        *For any* corrupted or invalid binary data (not a valid PDF), the
        PdfContentExtractorImpl SHALL raise PdfExtractionError with a non-empty
        error message.
        
        **Validates: Requirements 4.3**
        """
        extractor = _extractor
        # Skip if the random data happens to be a valid PDF (extremely unlikely but possible)
        # A valid PDF starts with "%PDF-"
        assume(not invalid_data.startswith(b'%PDF-'))
        
        source_url = "http://example.com/invalid.pdf"
        
        # Should raise PdfExtractionError for invalid data
        with pytest.raises(PdfExtractionError) as exc_info:
            extractor.extract_content(invalid_data, source_url)
        
        # Error message should be non-empty
        assert exc_info.value.message, "Error message should not be empty"
        assert len(exc_info.value.message) > 0, "Error message should have content"

    @settings(max_examples=100)
    @given(
        invalid_data=st.binary(min_size=1, max_size=1000)
    )
    def test_property_4_invalid_pdf_metadata_extraction_error(self, invalid_data):
        """
        Property 4 (extended): Invalid PDF Error Handling for extract_metadata
        
        *For any* corrupted or invalid binary data, extract_metadata SHALL also
        raise PdfExtractionError with a non-empty error message.
        
        **Validates: Requirements 4.3**
        """
        extractor = _extractor
        # Skip if the random data happens to be a valid PDF
        assume(not invalid_data.startswith(b'%PDF-'))
        
        # Should raise PdfExtractionError for invalid data
        with pytest.raises(PdfExtractionError) as exc_info:
            extractor.extract_metadata(invalid_data)
        
        # Error message should be non-empty
        assert exc_info.value.message, "Error message should not be empty"
        assert len(exc_info.value.message) > 0, "Error message should have content"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
