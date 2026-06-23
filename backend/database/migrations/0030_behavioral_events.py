"""
Migration 0030: behavioral event log (T-API-053).

Captures the explicit / implicit / outcome signals from ARCHITECTURE.md §7.5 on
MySQL now, so there is training data ready when the ML loops (Loop 1/2/3) and
the Redpanda event bus (T-API-031) come online. Append-only, fire-and-forget.
"""


def up(conn):
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS `lu_behavioral_events` (
              `id` VARCHAR(36) NOT NULL,
              `account_id` VARCHAR(36) NULL,
              `verb` VARCHAR(40) NOT NULL,
              `object_type` VARCHAR(40) NULL,
              `object_id` VARCHAR(36) NULL,
              `context` JSON NULL,
              `created_at` DATETIME NULL,
              PRIMARY KEY (`id`),
              KEY `idx_bev_account` (`account_id`),
              KEY `idx_bev_verb` (`verb`),
              KEY `idx_bev_created` (`created_at`)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)
    conn.commit()


def down(conn):
    with conn.cursor() as cur:
        cur.execute("DROP TABLE IF EXISTS `lu_behavioral_events`")
    conn.commit()
