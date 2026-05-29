"""Database schema migration tests (SQLite)."""

from __future__ import annotations

import os
import tempfile
import unittest

from constants import WHATSAPP_APP_TYPE_COLUMN, WHATSAPP_SENDER_PHONE_COLUMN


class SchemaMigrationTests(unittest.TestCase):
    def test_family_whatsapp_columns_exist_after_migration(self) -> None:
        import database as db

        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "test.db")
            original_file = db.DATABASE_FILE if hasattr(db, "DATABASE_FILE") else None

            # Point at temp sqlite file
            from constants import DATABASE_FILE

            old_path = DATABASE_FILE
            try:
                import constants

                constants.DATABASE_FILE = db_path
                db.invalidate_families_cache = lambda: None  # noqa: no streamlit in tests

                with db.db_connection() as connection:
                    db._run_schema_init(connection)

                with db.db_connection() as connection:
                    row = connection.execute(
                        f"""
                        SELECT {WHATSAPP_SENDER_PHONE_COLUMN}, {WHATSAPP_APP_TYPE_COLUMN}
                        FROM family
                        """
                    ).fetchone()
                    self.assertIsNotNone(row)
                    version = connection.execute(
                        "SELECT version FROM schema_version LIMIT 1"
                    ).fetchone()
                    self.assertEqual(int(version["version"]), db._SCHEMA_VERSION)
            finally:
                constants.DATABASE_FILE = old_path


if __name__ == "__main__":
    unittest.main()
