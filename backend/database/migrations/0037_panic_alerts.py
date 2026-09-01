"""
Migration 0037: lu_panic_alerts — persistent SOS/panic event log.

POST /v1/safety/panic used to fire notifications and vanish with no queryable
record. This table is what the new admin safety dashboard reads.
"""


def up(conn):
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS `lu_panic_alerts` (
                `id`                 VARCHAR(36)  NOT NULL,
                `account_id`         VARCHAR(36)  NOT NULL,
                `checkin_id`         VARCHAR(36)  DEFAULT NULL,
                `location_text`      VARCHAR(500) DEFAULT NULL,
                `contacts_notified`  INT          NOT NULL DEFAULT 0,
                `status`             VARCHAR(20)  NOT NULL DEFAULT 'open',
                `resolved_by`        VARCHAR(36)  DEFAULT NULL,
                `resolved_at`        DATETIME     DEFAULT NULL,
                `resolution_note`    TEXT         DEFAULT NULL,
                `created_at`         TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (`id`),
                KEY `idx_panic_account` (`account_id`),
                KEY `idx_panic_status` (`status`),
                CONSTRAINT `fk_panic_account` FOREIGN KEY (`account_id`)
                    REFERENCES `lu_accounts`(`id`) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
    conn.commit()


def down(conn):
    with conn.cursor() as cur:
        cur.execute("DROP TABLE IF EXISTS `lu_panic_alerts`")
    conn.commit()
