"""
Migration 0026: Repair double-encoded `modes_enabled` on lu_accounts.

Some seeded accounts stored `modes_enabled` as a JSON *string*
(e.g. '"{\\"professional\\": true, \\"sparks\\": true}"') inside the JSON
column instead of a JSON object. Reading such a row yields a Python `str`,
which crashes any code that calls `.get()` on it (see T-API-040 / defect D-1).

This migration unwraps the string back into a proper JSON object. It loops
to defensively handle values that were encoded more than once.
"""


def up(conn):
    with conn.cursor() as cur:
        for _ in range(5):  # tolerate multiply-encoded values
            cur.execute(
                "SELECT COUNT(*) FROM lu_accounts "
                "WHERE JSON_TYPE(modes_enabled) = 'STRING'"
            )
            remaining = cur.fetchone()[0]
            if not remaining:
                break
            # JSON_UNQUOTE turns the JSON-string back into raw JSON text;
            # assigning valid JSON text to a JSON column re-parses it as an object.
            cur.execute(
                "UPDATE lu_accounts "
                "SET modes_enabled = JSON_UNQUOTE(modes_enabled) "
                "WHERE JSON_TYPE(modes_enabled) = 'STRING'"
            )
    conn.commit()


def down(conn):
    # No-op: re-introducing the corruption is intentionally not supported.
    pass
