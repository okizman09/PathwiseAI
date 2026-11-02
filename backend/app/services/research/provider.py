"""Research provider interface (Catalog v3).

Provider-agnostic interface allowing future automated research providers
(e.g., Perplexity, Google Search, Crawl4AI) to be plugged in without
tight coupling.
"""
from abc import ABC, abstractmethod
from typing import Any


class ResearchProvider(ABC):
    """Abstract interface for external tool research providers."""

    @abstractmethod
    async def research_tool(
        self,
        name: str,
        domain: str,
        official_url: str,
        pricing_url: str | None = None,
        docs_url: str | None = None,
    ) -> dict[str, Any]:
        """Perform research on a tool and return structured card data matching section 3."""
        raise NotImplementedError
