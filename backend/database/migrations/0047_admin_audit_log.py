"""
Migration 0047: lu_admin_audit_log — who did what to which account, when.

Sensitive admin actions (KYC decisions, account status changes, premium
grants) previously left no trail — an admin could suspend or premium-grant
any account with zero record of who did it or why.
"""


def up(conn):
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS `lu_admin_audit_log` (
                `id`            VARCHAR(36)  NOT NULL,
                `admin_id`      VARCHAR(36)  NOT NULL,
                `action`        VARCHAR(60)  NOT NULL,
                `target_account_id` VARCHAR(36) DEFAULT NULL,
                `detail`        JSON NULL,
                `created_at`    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (`id`),
                KEY `idx_audit_admin` (`admin_id`),
                KEY `idx_audit_target` (`target_account_id`),
                CONSTRAINT `fk_audit_admin` FOREIGN KEY (`admin_id`)
                    REFERENCES `lu_accounts`(`id`) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
    conn.commit()


def down(conn):
    with conn.cursor() as cur:
        cur.execute("DROP TABLE IF EXISTS `lu_admin_audit_log`")
    conn.commit()
