"""Load cross references, lexicon entries, topics, reading plans, and devotional templates."""
from __future__ import annotations

import sys
from pathlib import Path

# Add the parent directory of the script (backend/) to sys.path
script_dir = Path(__file__).resolve().parent
project_root = script_dir.parent
sys.path.insert(0, str(project_root))

import argparse
import json
import logging
from pathlib import Path
from typing import Any, Iterable, Sequence

from app.database import get_db_connection

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger("study-resource-import")

DEFAULT_DATA_DIR = Path(__file__).resolve().parent.parent / "app" / "data" / "reference_data"


def _load_json(path: Path) -> Sequence[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def import_cross_references(data: Sequence[dict[str, Any]]) -> None:
    logger.info("Importing %s cross reference rows", len(data))
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("TRUNCATE cross_references RESTART IDENTITY CASCADE;")
            for entry in data:
                cur.execute(
                    """
                    INSERT INTO cross_references (book, chapter, verse, reference_data)
                    VALUES (%s, %s, %s, %s::jsonb)
                    """,
                    (
                        entry["book"],
                        entry["chapter"],
                        entry["verse"],
                        json.dumps(entry.get("references", []))
                    ),
                )
        conn.commit()


def import_lexicon_entries(data: Sequence[dict[str, Any]]) -> None:
    logger.info("Importing %s lexicon entries", len(data))
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("TRUNCATE lexicon_entries RESTART IDENTITY CASCADE;")
            for entry in data:
                cur.execute(
                    """
                    INSERT INTO lexicon_entries (
                        strongs_number,
                        lemma,
                        transliteration,
                        pronunciation,
                        language,
                        definition,
                        usage,
                        reference_list,
                        metadata
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb)
                    """,
                    (
                        entry["strongs_number"],
                        entry["lemma"],
                        entry.get("transliteration"),
                        entry.get("pronunciation"),
                        entry.get("language"),
                        entry.get("definition"),
                        entry.get("usage"),
                        json.dumps(entry.get("references", [])),
                        json.dumps(entry.get("metadata", {}))
                    ),
                )
        conn.commit()


def import_topic_index(data: Sequence[dict[str, Any]]) -> None:
    logger.info("Importing %s topical entries", len(data))
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("TRUNCATE topic_index RESTART IDENTITY CASCADE;")
            for entry in data:
                cur.execute(
                    """
                    INSERT INTO topic_index (topic, summary, keywords, reference_entries)
                    VALUES (%s, %s, %s, %s::jsonb)
                    """,
                    (
                        entry["topic"],
                        entry.get("summary"),
                        entry.get("keywords", []),
                        json.dumps(entry.get("references", []))
                    ),
                )
        conn.commit()


def import_reading_plans(data: Sequence[dict[str, Any]]) -> None:
    logger.info("Importing %s reading plans", len(data))
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("TRUNCATE reading_plan_entries RESTART IDENTITY CASCADE;")
            cur.execute("TRUNCATE reading_plans RESTART IDENTITY CASCADE;")
            for plan in data:
                cur.execute(
                    """
                    INSERT INTO reading_plans (slug, name, description, duration_days, metadata)
                    VALUES (%s, %s, %s, %s, %s::jsonb)
                    RETURNING id
                    """,
                    (
                        plan["slug"],
                        plan["name"],
                        plan.get("description"),
                        plan["duration_days"],
                        json.dumps(plan.get("metadata", {}))
                    ),
                )
                plan_id = cur.fetchone()["id"]
                for step in plan.get("steps", []):
                    cur.execute(
                        """
                        INSERT INTO reading_plan_entries (
                            plan_id,
                            day_number,
                            title,
                            passage,
                            notes,
                            metadata
                        )
                        VALUES (%s, %s, %s, %s, %s, %s::jsonb)
                        """,
                        (
                            plan_id,
                            step["day"],
                            step["title"],
                            step["passage"],
                            step.get("notes"),
                            json.dumps(step.get("metadata", {}))
                        ),
                    )
        conn.commit()


def import_devotional_templates(data: Sequence[dict[str, Any]]) -> None:
    logger.info("Importing %s devotional templates", len(data))
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("TRUNCATE devotional_templates RESTART IDENTITY CASCADE;")
            for template in data:
                cur.execute(
                    """
                    INSERT INTO devotional_templates (
                        slug,
                        title,
                        body,
                        prompt_1,
                        prompt_2,
                        default_passage,
                        metadata
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb)
                    """,
                    (
                        template["slug"],
                        template["title"],
                        template["body"],
                        template["prompt_1"],
                        template["prompt_2"],
                        template.get("default_passage"),
                        json.dumps(template.get("metadata", {}))
                    ),
                )
        conn.commit()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import reference datasets for MCP study tools")
    parser.add_argument(
        "--data-dir",
        default=str(DEFAULT_DATA_DIR),
        help="Directory containing cross_references.json, lexicon_entries.json, topic_index.json, reading_plans.json, and devotional_templates.json",
    )
    parser.add_argument(
        "--skip",
        nargs="*",
        default=(),
        choices=["cross", "lexicon", "topics", "plans", "devotionals"],
        help="Datasets to skip importing",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    data_dir = Path(args.data_dir).expanduser().resolve()
    if not data_dir.exists():
        raise SystemExit(f"Data directory {data_dir} does not exist")

    logger.info("Using data directory: %s", data_dir)

    dataset_map = {
        "cross": ("cross_references.json", import_cross_references),
        "lexicon": ("lexicon_entries.json", import_lexicon_entries),
        "topics": ("topic_index.json", import_topic_index),
        "plans": ("reading_plans.json", import_reading_plans),
        "devotionals": ("devotional_templates.json", import_devotional_templates),
    }

    for key, (filename, importer) in dataset_map.items():
        if key in args.skip:
            logger.info("Skipping %s dataset", key)
            continue

        path = data_dir / filename
        if not path.exists():
            raise SystemExit(f"Required dataset {filename} not found in {data_dir}")

        entries = _load_json(path)
        importer(entries)

    logger.info("Import complete")


if __name__ == "__main__":
    main()
