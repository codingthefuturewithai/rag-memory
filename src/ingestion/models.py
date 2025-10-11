"""Data models for web crawling results."""

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional


@dataclass
class CrawlError:
    """Represents an error that occurred during crawling."""

    url: str
    error_type: str
    error_message: str
    timestamp: datetime
    status_code: Optional[int] = None

    def to_dict(self) -> Dict:
        """Convert to dictionary representation."""
        return {
            "url": self.url,
            "error_type": self.error_type,
            "error_message": self.error_message,
            "timestamp": self.timestamp.isoformat(),
            "status_code": self.status_code,
        }


@dataclass
class CrawlResult:
    """Represents the result of crawling a single page."""

    url: str
    content: str
    metadata: Dict
    success: bool
    error: Optional[CrawlError] = None
    links_found: Optional[List[str]] = None

    def to_dict(self) -> Dict:
        """Convert to dictionary representation."""
        result = {
            "url": self.url,
            "content": self.content,
            "metadata": self.metadata,
            "success": self.success,
        }
        if self.error:
            result["error"] = self.error.to_dict()
        if self.links_found is not None:
            result["links_found"] = self.links_found
        return result


@dataclass
class BatchCrawlResult:
    """Represents the result of crawling multiple pages."""

    crawl_root_url: str
    crawl_session_id: str
    crawl_timestamp: datetime
    successful_pages: List[CrawlResult]
    failed_pages: List[CrawlError]
    total_pages_attempted: int
    total_pages_succeeded: int
    total_pages_failed: int

    def to_dict(self) -> Dict:
        """Convert to dictionary representation."""
        return {
            "crawl_root_url": self.crawl_root_url,
            "crawl_session_id": self.crawl_session_id,
            "crawl_timestamp": self.crawl_timestamp.isoformat(),
            "successful_pages": [page.to_dict() for page in self.successful_pages],
            "failed_pages": [error.to_dict() for error in self.failed_pages],
            "total_pages_attempted": self.total_pages_attempted,
            "total_pages_succeeded": self.total_pages_succeeded,
            "total_pages_failed": self.total_pages_failed,
        }
