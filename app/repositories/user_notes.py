"""Repository for storing and retrieving user-authored study notes."""
import json
from typing import Any

from app.database import get_db_connection


class UserNotesRepository:
    """Repository for storing and retrieving user-authored study notes."""

    @staticmethod
    def create_note(
        user_id: int,
        content: str,
        question_id: int | None = None,
        metadata: dict | None = None,
        source: str | None = None,
    ) -> dict:
        """Persist a note linked to an optional question reference."""
        metadata_json = json.dumps(metadata) if metadata is not None else None

        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO user_notes (user_id, question_id, content, metadata, source)
                    VALUES (%s, %s, %s, %s::jsonb, %s)
                    RETURNING id, user_id, question_id, content, metadata, source, created_at, updated_at
                    """,
                    (user_id, question_id, content, metadata_json, source),
                )
                note = cur.fetchone()
                conn.commit()
                if note and isinstance(note.get("metadata"), str):
                    note["metadata"] = json.loads(note["metadata"])
                return note

    @staticmethod
    def list_notes(user_id: int, question_id: int | None = None, limit: int = 50) -> list:
        """Return notes for a user filtered by question when provided."""
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                query = [
                    "SELECT id, user_id, question_id, content, metadata, source, created_at, updated_at",
                    "FROM user_notes",
                    "WHERE user_id = %s",
                ]
                params: list[Any] = [user_id]

                if question_id is not None:
                    query.append("AND question_id = %s")
                    params.append(question_id)

                query.append("ORDER BY created_at DESC LIMIT %s")
                params.append(limit)

                cur.execute("\n".join(query), tuple(params))
                rows = cur.fetchall()
                for row in rows:
                    if isinstance(row.get("metadata"), str):
                        row["metadata"] = json.loads(row["metadata"])
                return rows
