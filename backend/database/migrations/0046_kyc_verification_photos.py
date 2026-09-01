"""
Migration 0046: lu_verifications gets real evidence columns.

Previously KYC L1->L2 only stored a self-reported ID number string inside a
JSON `metadata` blob (built via unsafe f-string interpolation, not
json.dumps) -- admins reviewing the KYC queue had no photo to actually look
at, just a raw string. Adds dedicated id_photo_url/selfie_url/rejection_reason
columns (mirroring lu_listing_claims.liveness_capture_path -- a real column,
not JSON-buried) and widens `type` to include 'national_id', the only value
the code has ever actually inserted (the original ENUM never included it).
"""


def _has_column(cur, table, column):
    cur.execute(
        "SELECT COUNT(*) FROM information_schema.COLUMNS "
        "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s AND COLUMN_NAME = %s",
        (table, column)
    )
    return cur.fetchone()[0] > 0


def up(conn):
    with conn.cursor() as cur:
        if not _has_column(cur, 'lu_verifications', 'id_photo_url'):
            cur.execute(
                "ALTER TABLE `lu_verifications` "
                "ADD COLUMN `id_photo_url` VARCHAR(500) DEFAULT NULL AFTER `metadata`")
        if not _has_column(cur, 'lu_verifications', 'selfie_url'):
            cur.execute(
                "ALTER TABLE `lu_verifications` "
                "ADD COLUMN `selfie_url` VARCHAR(500) DEFAULT NULL AFTER `id_photo_url`")
        if not _has_column(cur, 'lu_verifications', 'rejection_reason'):
            cur.execute(
                "ALTER TABLE `lu_verifications` "
                "ADD COLUMN `rejection_reason` VARCHAR(500) DEFAULT NULL AFTER `selfie_url`")
        if not _has_column(cur, 'lu_verifications', 'reviewed_by'):
            cur.execute(
                "ALTER TABLE `lu_verifications` "
                "ADD COLUMN `reviewed_by` VARCHAR(36) DEFAULT NULL AFTER `rejection_reason`")
        cur.execute(
            "ALTER TABLE `lu_verifications` "
            "MODIFY COLUMN `type` ENUM('phone','email','id_card','passport',"
            "'degree','employment','national_id') NOT NULL DEFAULT 'phone'")
    conn.commit()


def down(conn):
    with conn.cursor() as cur:
        for col in ('id_photo_url', 'selfie_url', 'rejection_reason', 'reviewed_by'):
            try:
                cur.execute(f"ALTER TABLE `lu_verifications` DROP COLUMN IF EXISTS `{col}`")
            except Exception:
                pass
        cur.execute(
            "ALTER TABLE `lu_verifications` "
            "MODIFY COLUMN `type` ENUM('phone','email','id_card','passport',"
            "'degree','employment') NOT NULL DEFAULT 'phone'")
    conn.commit()
