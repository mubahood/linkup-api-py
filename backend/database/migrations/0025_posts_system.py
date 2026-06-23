"""
Migration 0025: Universal posts system.

lu_posts             — universal post (text / photo / article / poll / job_share / event_share / share)
lu_post_likes        — per-post reactions (like / love / insightful / celebrate / support)
lu_post_comments     — comments + threaded replies (parent_id for replies)
lu_post_comment_likes — likes on comments
lu_post_saves        — saved / bookmarked posts
lu_poll_votes        — one vote per user per poll post

Design notes:
  • mode (professional | dating | both) controls which feed a post appears in.
  • audience (public | connections | only_me) controls visibility.
  • hub_id links a post to a community (optional).
  • linked_post_id enables reshares without a hard FK (to keep rollback simple).
  • Engagement counts (likes_count etc.) are denormalised for fast reads.
"""


def up(conn):
    c = conn.cursor()

    # ── lu_posts ──────────────────────────────────────────────────────────────
    try:
        c.execute("""
            CREATE TABLE IF NOT EXISTS lu_posts (
                id                VARCHAR(36)   NOT NULL,
                author_id         VARCHAR(36)   NOT NULL,
                mode              VARCHAR(20)   NOT NULL DEFAULT 'professional',
                post_type         VARCHAR(20)   NOT NULL DEFAULT 'text',
                body              TEXT          NULL,
                title             VARCHAR(300)  NULL,
                audience          VARCHAR(20)   NOT NULL DEFAULT 'public',
                hub_id            VARCHAR(36)   NULL,
                linked_job_id     VARCHAR(36)   NULL,
                linked_event_id   VARCHAR(36)   NULL,
                linked_post_id    VARCHAR(36)   NULL,
                media             JSON          NULL,
                tags              JSON          NULL,
                poll_question     VARCHAR(300)  NULL,
                poll_options      JSON          NULL,
                poll_ends_at      DATETIME      NULL,
                likes_count       INT           NOT NULL DEFAULT 0,
                comments_count    INT           NOT NULL DEFAULT 0,
                shares_count      INT           NOT NULL DEFAULT 0,
                views_count       INT           NOT NULL DEFAULT 0,
                is_pinned         TINYINT(1)    NOT NULL DEFAULT 0,
                is_edited         TINYINT(1)    NOT NULL DEFAULT 0,
                is_featured       TINYINT(1)    NOT NULL DEFAULT 0,
                moderation_status VARCHAR(20)   NOT NULL DEFAULT 'approved',
                created_at        DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at        DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP
                                                ON UPDATE CURRENT_TIMESTAMP,
                deleted_at        DATETIME      NULL,
                PRIMARY KEY (id),
                CONSTRAINT fk_post_author
                    FOREIGN KEY (author_id) REFERENCES lu_accounts(id) ON DELETE CASCADE,
                CONSTRAINT fk_post_hub
                    FOREIGN KEY (hub_id)    REFERENCES lu_hubs(id)     ON DELETE SET NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
    except Exception:
        pass

    # ── lu_post_likes ─────────────────────────────────────────────────────────
    try:
        c.execute("""
            CREATE TABLE IF NOT EXISTS lu_post_likes (
                id            VARCHAR(36) NOT NULL,
                post_id       VARCHAR(36) NOT NULL,
                account_id    VARCHAR(36) NOT NULL,
                reaction_type VARCHAR(20) NOT NULL DEFAULT 'like',
                created_at    DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (id),
                UNIQUE KEY uq_post_like (post_id, account_id),
                CONSTRAINT fk_plike_post    FOREIGN KEY (post_id)    REFERENCES lu_posts(id)    ON DELETE CASCADE,
                CONSTRAINT fk_plike_account FOREIGN KEY (account_id) REFERENCES lu_accounts(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
    except Exception:
        pass

    # ── lu_post_comments ──────────────────────────────────────────────────────
    try:
        c.execute("""
            CREATE TABLE IF NOT EXISTS lu_post_comments (
                id          VARCHAR(36) NOT NULL,
                post_id     VARCHAR(36) NOT NULL,
                author_id   VARCHAR(36) NOT NULL,
                parent_id   VARCHAR(36) NULL,
                body        TEXT        NOT NULL,
                likes_count INT         NOT NULL DEFAULT 0,
                is_edited   TINYINT(1)  NOT NULL DEFAULT 0,
                created_at  DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at  DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP
                                        ON UPDATE CURRENT_TIMESTAMP,
                deleted_at  DATETIME    NULL,
                PRIMARY KEY (id),
                CONSTRAINT fk_pcomment_post   FOREIGN KEY (post_id)   REFERENCES lu_posts(id)    ON DELETE CASCADE,
                CONSTRAINT fk_pcomment_author FOREIGN KEY (author_id) REFERENCES lu_accounts(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
    except Exception:
        pass

    # ── lu_post_comment_likes ─────────────────────────────────────────────────
    try:
        c.execute("""
            CREATE TABLE IF NOT EXISTS lu_post_comment_likes (
                id         VARCHAR(36) NOT NULL,
                comment_id VARCHAR(36) NOT NULL,
                account_id VARCHAR(36) NOT NULL,
                created_at DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (id),
                UNIQUE KEY uq_comment_like (comment_id, account_id),
                CONSTRAINT fk_clike_comment FOREIGN KEY (comment_id) REFERENCES lu_post_comments(id) ON DELETE CASCADE,
                CONSTRAINT fk_clike_account FOREIGN KEY (account_id) REFERENCES lu_accounts(id)      ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
    except Exception:
        pass

    # ── lu_post_saves ─────────────────────────────────────────────────────────
    try:
        c.execute("""
            CREATE TABLE IF NOT EXISTS lu_post_saves (
                id         VARCHAR(36) NOT NULL,
                post_id    VARCHAR(36) NOT NULL,
                account_id VARCHAR(36) NOT NULL,
                created_at DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (id),
                UNIQUE KEY uq_post_save (post_id, account_id),
                CONSTRAINT fk_psave_post    FOREIGN KEY (post_id)    REFERENCES lu_posts(id)    ON DELETE CASCADE,
                CONSTRAINT fk_psave_account FOREIGN KEY (account_id) REFERENCES lu_accounts(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
    except Exception:
        pass

    # ── lu_poll_votes ─────────────────────────────────────────────────────────
    try:
        c.execute("""
            CREATE TABLE IF NOT EXISTS lu_poll_votes (
                id         VARCHAR(36) NOT NULL,
                post_id    VARCHAR(36) NOT NULL,
                account_id VARCHAR(36) NOT NULL,
                option_id  VARCHAR(50) NOT NULL,
                created_at DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (id),
                UNIQUE KEY uq_poll_vote (post_id, account_id),
                CONSTRAINT fk_pvote_post    FOREIGN KEY (post_id)    REFERENCES lu_posts(id)    ON DELETE CASCADE,
                CONSTRAINT fk_pvote_account FOREIGN KEY (account_id) REFERENCES lu_accounts(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
    except Exception:
        pass

    # ── Indexes ───────────────────────────────────────────────────────────────
    for idx_sql in [
        "CREATE INDEX idx_posts_author   ON lu_posts (author_id)",
        "CREATE INDEX idx_posts_mode     ON lu_posts (mode)",
        "CREATE INDEX idx_posts_created  ON lu_posts (created_at DESC)",
        "CREATE INDEX idx_posts_hub      ON lu_posts (hub_id)",
        "CREATE INDEX idx_posts_audience ON lu_posts (audience)",
        "CREATE INDEX idx_pcomments_post ON lu_post_comments (post_id)",
        "CREATE INDEX idx_pcomments_par  ON lu_post_comments (parent_id)",
        "CREATE INDEX idx_plikes_post    ON lu_post_likes (post_id)",
        "CREATE INDEX idx_psaves_acct    ON lu_post_saves (account_id)",
        "CREATE INDEX idx_pvotes_post    ON lu_poll_votes (post_id)",
    ]:
        try:
            c.execute(idx_sql)
        except Exception:
            pass

    conn.commit()


def down(conn):
    c = conn.cursor()
    for table in [
        'lu_poll_votes', 'lu_post_saves', 'lu_post_comment_likes',
        'lu_post_comments', 'lu_post_likes', 'lu_posts',
    ]:
        try:
            c.execute(f"DROP TABLE IF EXISTS {table}")
        except Exception:
            pass
    conn.commit()
