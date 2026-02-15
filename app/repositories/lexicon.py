"""Repository for lexical lookup data (Strong's style)."""
import json
from typing import Any, List, Optional

from app.database import get_db_connection


class LexiconRepository:
    """Repository for lexical lookup data (Strong's style)."""

    @staticmethod
    def get_entry(strongs_number: Optional[str] = None, lemma: Optional[str] = None) -> Optional[dict[str, Any]]:
        if not strongs_number and not lemma:
            return None

        query = [
            "SELECT strongs_number, lemma, transliteration, pronunciation, language, definition, usage, reference_list, metadata",
            "FROM lexicon_entries",
        ]
        clauses: List[str] = []
        params: List[Any] = []

        if strongs_number:
            clauses.append("LOWER(strongs_number) = LOWER(%s)")
            params.append(strongs_number)

        if lemma:
            clauses.append("lemma ILIKE %s")
            params.append(f"%{lemma}%")

        if clauses:
            query.append("WHERE " + " AND ".join(clauses))

        query.append("ORDER BY created_at ASC LIMIT 1")

        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("\n".join(query), tuple(params))
                row = cur.fetchone()
                if not row:
                    return None

                references = row.pop("reference_list", [])
                metadata = row.get("metadata")
                if isinstance(references, str):
                    references = json.loads(references)
                if isinstance(metadata, str):
                    metadata = json.loads(metadata)
                    row["metadata"] = metadata
                row["references"] = references
                return row
