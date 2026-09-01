"""
Migration 0035: App version / force-update config.

One row per (app_id, platform). Drives GET /v1/app/version — the backend is
the single source of truth for whether a build must update, computed as
`installed_build < min_supported_build`. Seeded with each app's real current
build so nothing is forced until min_supported_build is deliberately raised
for a future release.
"""


def up(conn):
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS `lu_app_versions` (
                `id`                  VARCHAR(36)  NOT NULL,
                `app_id`              VARCHAR(20)  NOT NULL,
                `platform`            VARCHAR(10)  NOT NULL,
                `latest_build`        INT          NOT NULL,
                `latest_version_name` VARCHAR(20)  NOT NULL,
                `min_supported_build` INT          NOT NULL,
                `update_notes`        TEXT         NULL,
                `android_url`         VARCHAR(500) NULL,
                `ios_url`             VARCHAR(500) NULL,
                `updated_at`          TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP
                                                    ON UPDATE CURRENT_TIMESTAMP,
                PRIMARY KEY (`id`),
                UNIQUE KEY `uq_app_platform` (`app_id`, `platform`)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)

        # ios_url left NULL — neither app is on the App Store yet. Fill it in
        # (UPDATE lu_app_versions SET ios_url=... WHERE app_id=... AND platform='ios')
        # once each app has a real App Store listing; until then iOS just never
        # gets a store link to open (the update screen should handle that gracefully).
        rows = [
            ('abanoonya', 'android', 2, '1.0.0', 1,
             'Bug fixes and performance improvements.',
             'https://play.google.com/store/apps/details?id=app.abanoonya.pro', None),
            ('abanoonya', 'ios', 1, '1.0.0', 1,
             'Bug fixes and performance improvements.', None, None),
            ('linkup', 'android', 17, '3.0.16', 1,
             'Bug fixes and performance improvements.',
             'https://play.google.com/store/apps/details?id=app.linkup.mobile', None),
            ('linkup', 'ios', 1, '3.0.16', 1,
             'Bug fixes and performance improvements.', None, None),
        ]
        for app_id, platform, latest_build, latest_version_name, min_build, notes, android_url, ios_url in rows:
            cur.execute(
                "INSERT IGNORE INTO `lu_app_versions` "
                "(`id`, `app_id`, `platform`, `latest_build`, `latest_version_name`, "
                "`min_supported_build`, `update_notes`, `android_url`, `ios_url`) "
                "VALUES (UUID(), %s, %s, %s, %s, %s, %s, %s, %s)",
                (app_id, platform, latest_build, latest_version_name, min_build, notes, android_url, ios_url)
            )

    conn.commit()


def down(conn):
    with conn.cursor() as cur:
        cur.execute("DROP TABLE IF EXISTS `lu_app_versions`")
    conn.commit()
