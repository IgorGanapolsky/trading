"""
Research module for trading system.

Contains:
- messy_document_parser: multi-format cascade (PDF/HTML/text + quality gate)
- docling_parser: IBM Docling integration for parsing financial documents
- research_agent: Perplexity-powered weekend research agent
"""

from src.research.docling_parser import (
    DoclingDocument,
    DoclingFinancialParser,
    FinancialMetrics,
    ParsedSection,
    ParsedTable,
    get_docling_parser,
)
from src.research.messy_document_parser import (
    ParsedDocument,
    available_backends,
    parse_document,
    parse_to_rag_payload,
)

__all__ = [
    "DoclingDocument",
    "DoclingFinancialParser",
    "FinancialMetrics",
    "ParsedDocument",
    "ParsedSection",
    "ParsedTable",
    "available_backends",
    "get_docling_parser",
    "parse_document",
    "parse_to_rag_payload",
]
