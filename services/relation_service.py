"""
RelationService - Service for computing thought chains (related notes).

This service finds related notes based on common tags and sorts them by:
1. Number of common tags (descending)
2. Date created (newest first)
"""

import asyncio
import logging
import time
from datetime import datetime
from typing import List, Dict, Any, Optional
from storage.google_sheets import GoogleSheetsStorage


class RelationService:
    """Service for computing relationships between notes based on tags."""

    def __init__(self, storage: GoogleSheetsStorage):
        """
        Initialize the relation service.

        Args:
            storage: GoogleSheetsStorage instance for data access
        """
        self.storage = storage
        self.logger = logging.getLogger(__name__)

    async def get_related_notes(
        self,
        note_id: str,
        spreadsheet_id: str
    ) -> List[Dict[str, Any]]:
        """
        Get all notes related to the given note through common tags.

        Args:
            note_id: The ID of the target note (Column A in Google Sheets)
            spreadsheet_id: The user's spreadsheet ID

        Returns:
            List of related notes with additional 'common_tags_count' field,
            sorted by common tags count (desc) and then by date (newest first)
        """
        start_time = time.time()

        try:
            # Fetch all notes using thread pool (sync method)
            all_notes = await asyncio.to_thread(
                self.storage._get_all_notes_sync,
                spreadsheet_id
            )

            # Parse notes and find target
            parsed_notes = self._parse_notes(all_notes)
            target_note = self._find_note_by_id(note_id, parsed_notes)

            if not target_note:
                self.logger.warning(f"Note {note_id} not found in spreadsheet {spreadsheet_id}")
                return []

            # If target has no tags, no relations possible
            target_tags = self._parse_tags(target_note.get('tags', ''))
            if not target_tags:
                self.logger.info(f"Note {note_id} has no tags, no relations")
                return []

            # Compute related notes
            related = self._compute_related_notes(target_note, parsed_notes)

            elapsed = time.time() - start_time
            self.logger.info(
                f"Related notes computation: {elapsed:.3f}s for {len(related)} "
                f"related notes (out of {len(parsed_notes)} total)"
            )

            return related

        except Exception as e:
            self.logger.error(f"Error computing related notes: {e}", exc_info=True)
            raise

    def _parse_notes(self, raw_notes: List[List[str]]) -> List[Dict[str, Any]]:
        """
        Parse raw Google Sheets rows into structured note dictionaries.

        Args:
            raw_notes: List of rows from Google Sheets

        Returns:
            List of parsed note dictionaries
        """
        notes = []
        for row in raw_notes:
            if len(row) >= 9:
                note = {
                    'id': row[0],
                    'telegram_message_id': row[1],
                    'created_at': row[2],
                    'content': row[3],
                    'tags': row[4],
                    'reply_to_message_id': row[5] if row[5] else None,
                    'message_type': row[6],
                    'source_chat_id': row[7] if row[7] else None,
                    'source_chat_link': row[8] if row[8] else None,
                    'telegram_username': row[9] if len(row) > 9 and row[9] else None,
                    'status': row[10] if len(row) > 10 else ''
                }
                notes.append(note)
        return notes

    def _find_note_by_id(
        self,
        note_id: str,
        notes: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """
        Find a note by its ID.

        Args:
            note_id: The note ID to search for
            notes: List of parsed notes

        Returns:
            Note dictionary or None if not found
        """
        for note in notes:
            if note['id'] == note_id:
                return note
        return None

    def _parse_tags(self, tags_str: str) -> List[str]:
        """
        Parse tags string into list of individual tags.

        Args:
            tags_str: Comma-separated tags string (e.g., "#tag1, #tag2")

        Returns:
            List of normalized tags
        """
        if not tags_str:
            return []

        # Split by comma and strip whitespace
        tags = [tag.strip() for tag in tags_str.split(',')]
        # Filter empty strings
        tags = [tag for tag in tags if tag]
        return tags

    def _compute_related_notes(
        self,
        target_note: Dict[str, Any],
        all_notes: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Compute related notes for the target note.

        Algorithm:
        1. Parse target note tags
        2. For each other note, count common tags
        3. Filter notes with at least 1 common tag
        4. Sort by: common_tags_count DESC, created_at DESC

        Args:
            target_note: The note to find relations for
            all_notes: All notes in the spreadsheet

        Returns:
            Sorted list of related notes with 'common_tags_count' field
        """
        target_tags = set(self._parse_tags(target_note['tags']))
        related_notes = []

        for note in all_notes:
            # Skip the target note itself
            if note['id'] == target_note['id']:
                continue

            # Parse note tags
            note_tags = set(self._parse_tags(note['tags']))

            # Count common tags
            common_tags = target_tags & note_tags
            common_count = len(common_tags)

            # Only include notes with at least 1 common tag
            if common_count > 0:
                # Add common_tags_count to the note
                note_with_count = {**note, 'common_tags_count': common_count}
                related_notes.append(note_with_count)

        # Sort: more common tags first, then newer first
        related_notes.sort(
            key=lambda x: (
                -x['common_tags_count'],  # More tags = higher priority (negative for DESC)
                -self._parse_timestamp(x['created_at'])  # Newer = higher priority
            )
        )

        return related_notes

    def _parse_timestamp(self, timestamp_str: str) -> float:
        """
        Parse ISO 8601 timestamp string to Unix timestamp.

        Args:
            timestamp_str: ISO 8601 formatted timestamp

        Returns:
            Unix timestamp (float) or 0 if parsing fails
        """
        try:
            dt = datetime.fromisoformat(timestamp_str)
            return dt.timestamp()
        except (ValueError, AttributeError):
            self.logger.warning(f"Failed to parse timestamp: {timestamp_str}")
            return 0.0
