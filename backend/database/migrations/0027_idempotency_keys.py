"""
Migration 0027: Idempotency-Key store (T-API-045).

Backs the `@idempotent` decorator: when a client sends an `Idempotency-Key`
header on a write, the (account_id, key) → response is recorded here so a retry
replays the original result instead of repeating the side-effect. Rows expire
after 24h.
"""


def up(conn):
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS `lu_idempotency_keys` (
              `id` VARCHAR(36) NOT NULL,
              `account_id` VARCHAR(36) NOT NULL,
              `idem_key` VARCHAR(255) NOT NULL,
              `method` VARCHAR(10) NOT NULL,
              `path` VARCHAR(500) NOT NULL,
              `status_code` INT NOT NULL DEFAULT 200,
              `response_body` MEDIUMTEXT NULL,
              `created_at` DATETIME NULL,
              `expires_at` DATETIME NULL,
              PRIMARY KEY (`id`),
              UNIQUE KEY `uq_account_idem_key` (`account_id`, `idem_key`),
              KEY `idx_expires_at` (`expires_at`)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)
    conn.commit()


def down(conn):
    with conn.cursor() as cur:
        cur.execute("DROP TABLE IF EXISTS `lu_idempotency_keys`")
    conn.commit()
