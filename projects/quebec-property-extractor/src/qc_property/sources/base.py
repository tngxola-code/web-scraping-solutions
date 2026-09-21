from abc import ABC, abstractmethod
from typing import Dict, Any, Iterator

class AssessmentSource(ABC):
    """Abstract base class for assessment roll data sources."""
    
    @abstractmethod
    def discover_records(self, scope: Dict[str, Any]) -> Iterator[Dict[str, Any]]:
        """Discover property records within the configured scope."""
        pass

    @abstractmethod
    def fetch_record(self, record_ref: Any) -> Dict[str, Any]:
        """Fetch raw data for a specific record."""
        pass

    @abstractmethod
    def parse_record(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse raw data into a mapped dictionary."""
        pass
