"""Read the ChatGPT export format.

The first implementation of the conversation source boundary (ARCHITECTURE.md §8), for the only
source the MVP has (§2). Specification: specs/008-chatgpt-export-source.
"""

from hermes_memory.ingestion.chatgpt.source import ChatGPTExportSource

__all__ = ["ChatGPTExportSource"]
