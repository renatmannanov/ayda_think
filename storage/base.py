from abc import ABC, abstractmethod
from typing import Dict, Any

class BaseStorage(ABC):
    """
    Abstract base class for storage backends.
    """
    
    @abstractmethod
    async def save_note(self, destination_id: str, note_data: Dict[str, Any]) -> str:
        """
        Saves a note to the storage.
        
        Args:
            destination_id: The ID of the destination (e.g., Spreadsheet ID).
            note_data: A dictionary containing note details (content, tags, etc.).
            
        Returns:
            The ID of the saved record.
        """
        pass
