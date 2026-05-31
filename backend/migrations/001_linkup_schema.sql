-- ============================================================
-- LinkUp Schema Migration 001
-- Uganda-first Professional Networking + Dating Platform
-- All tables prefixed lu_
-- ============================================================

SET NAMES utf8mb4;
SET foreign_key_checks = 0;

-- ─── Reference Tables ────────────────────────────────────────

CREATE TABLE IF NOT EXISTS lu_locations (
    id VARCHAR(36) PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    level ENUM('country', 'region', 'district', 'city', 'area') DEFAULT 'city',
    parent_id VARCHAR(36) NULL,
    country_code VARCHAR(10) DEFAULT 'UG',
    latitude DECIMAL(10,8) NULL,
    longitude DECIMAL(11,8) NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_lu_locations_parent (parent_id),
    INDEX idx_lu_locations_country (country_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS lu_institutions (
    id VARCHAR(36) PRIMARY KEY,
    name VARCHAR(300) NOT NULL,
    short_name VARCHAR(100) NULL,
    type ENUM('university', 'college', 'polytechnic', 'secondary', 'primary', 'other') DEFAULT 'university',
    country VARCHAR(100) DEFAULT 'Uganda',
    district VARCHAR(100) NULL,
    website VARCHAR(300) NULL,
    verified TINYINT(1) DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_lu_institutions_name (name(100))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS lu_orgs (
    id VARCHAR(36) PRIMARY KEY,
    name VARCHAR(300) NOT NULL,
    industry VARCHAR(200) NULL,
    size_range VARCHAR(50) NULL,
    website VARCHAR(300) NULL,
    verified TINYINT(1) DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_lu_orgs_name (name(100))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ─── Core Identity ───────────────────────────────────────────

CREATE TABLE IF NOT EXISTS lu_accounts (
    id VARCHAR(36) PRIMARY KEY,
    handle VARCHAR(100) UNIQUE NOT NULL,
    display_name VARCHAR(200) NOT NULL,
    phone VARCHAR(30) UNIQUE NOT NULL,
    email VARCHAR(300) UNIQUE NULL,
    phone_verified TINYINT(1) DEFAULT 0,
    email_verified TINYINT(1) DEFAULT 0,
    password_hash VARCHAR(500) NULL,
    kyc_level TINYINT DEFAULT 0,
    modes_enabled JSON NOT NULL,
    account_status ENUM('active', 'suspended', 'closed') DEFAULT 'active',
    reputation_score DECIMAL(5,2) DEFAULT 0.00,
    avatar VARCHAR(500) NULL,
    cover_photo VARCHAR(500) NULL,
    location_id VARCHAR(36) NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP NULL,
    INDEX idx_lu_accounts_phone (phone),
    INDEX idx_lu_accounts_handle (handle),
    INDEX idx_lu_accounts_status (account_status),
    FOREIGN KEY (location_id) REFERENCES lu_locations(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS lu_account_devices (
    id VARCHAR(36) PRIMARY KEY,
    account_id VARCHAR(36) NOT NULL,
    device_token VARCHAR(500) NULL,
    platform ENUM('ios', 'android', 'web') DEFAULT 'android',
    onesignal_player_id VARCHAR(200) NULL,
    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (account_id) REFERENCES lu_accounts(id) ON DELETE CASCADE,
    INDEX idx_lu_devices_account (account_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS lu_otp_requests (
    id VARCHAR(36) PRIMARY KEY,
    phone VARCHAR(30) NOT NULL,
    code_hash VARCHAR(500) NOT NULL,
    purpose ENUM('register', 'login', 'reset', 'verify') DEFAULT 'login',
    expires_at TIMESTAMP NOT NULL,
    verified_at TIMESTAMP NULL,
    attempts TINYINT DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_lu_otp_phone (phone),
    INDEX idx_lu_otp_expires (expires_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS lu_refresh_tokens (
    id VARCHAR(36) PRIMARY KEY,
    account_id VARCHAR(36) NOT NULL,
    token_hash VARCHAR(500) NOT NULL,
    device_id VARCHAR(36) NULL,
    expires_at TIMESTAMP NOT NULL,
    revoked_at TIMESTAMP NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (account_id) REFERENCES lu_accounts(id) ON DELETE CASCADE,
    INDEX idx_lu_refresh_account (account_id),
    INDEX idx_lu_refresh_hash (token_hash(100))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ─── Profiles ────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS lu_professional_profiles (
    id VARCHAR(36) PRIMARY KEY,
    account_id VARCHAR(36) NOT NULL UNIQUE,
    headline VARCHAR(500) NULL,
    bio TEXT NULL,
    seniority ENUM('student', 'entry', 'mid', 'senior', 'lead', 'executive', 'founder') DEFAULT 'entry',
    current_role VARCHAR(300) NULL,
    current_org_id VARCHAR(36) NULL,
    visibility_mode ENUM('public', 'members', 'links_only', 'self_only') DEFAULT 'public',
    open_to JSON NULL,
    location_id VARCHAR(36) NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (account_id) REFERENCES lu_accounts(id) ON DELETE CASCADE,
    FOREIGN KEY (current_org_id) REFERENCES lu_orgs(id) ON DELETE SET NULL,
    FOREIGN KEY (location_id) REFERENCES lu_locations(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS lu_dating_profiles (
    id VARCHAR(36) PRIMARY KEY,
    account_id VARCHAR(36) NOT NULL UNIQUE,
    display_name VARCHAR(200) NULL,
    bio TEXT NULL,
    age_min TINYINT DEFAULT 18,
    age_max TINYINT DEFAULT 40,
    intent ENUM('casual', 'serious', 'friendship', 'open') DEFAULT 'open',
    lifestyle JSON NULL,
    prompts JSON NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (account_id) REFERENCES lu_accounts(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS lu_education (
    id VARCHAR(36) PRIMARY KEY,
    account_id VARCHAR(36) NOT NULL,
    institution_id VARCHAR(36) NULL,
    institution_name VARCHAR(300) NULL,
    degree VARCHAR(200) NULL,
    field VARCHAR(200) NULL,
    start_year SMALLINT NULL,
    end_year SMALLINT NULL,
    verified TINYINT(1) DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (account_id) REFERENCES lu_accounts(id) ON DELETE CASCADE,
    FOREIGN KEY (institution_id) REFERENCES lu_institutions(id) ON DELETE SET NULL,
    INDEX idx_lu_education_account (account_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS lu_experience (
    id VARCHAR(36) PRIMARY KEY,
    account_id VARCHAR(36) NOT NULL,
    org_id VARCHAR(36) NULL,
    org_name VARCHAR(300) NULL,
    title VARCHAR(300) NOT NULL,
    description TEXT NULL,
    start_date DATE NULL,
    end_date DATE NULL,
    is_current TINYINT(1) DEFAULT 0,
    verified TINYINT(1) DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (account_id) REFERENCES lu_accounts(id) ON DELETE CASCADE,
    FOREIGN KEY (org_id) REFERENCES lu_orgs(id) ON DELETE SET NULL,
    INDEX idx_lu_experience_account (account_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS lu_certifications (
    id VARCHAR(36) PRIMARY KEY,
    account_id VARCHAR(36) NOT NULL,
    name VARCHAR(300) NOT NULL,
    issuer VARCHAR(300) NULL,
    issued_at DATE NULL,
    expires_at DATE NULL,
    credential_url VARCHAR(500) NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (account_id) REFERENCES lu_accounts(id) ON DELETE CASCADE,
    INDEX idx_lu_certifications_account (account_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ─── Interest Graph ───────────────────────────────────────────

CREATE TABLE IF NOT EXISTS lu_interest_tags (
    id VARCHAR(36) PRIMARY KEY,
    slug VARCHAR(200) UNIQUE NOT NULL,
    dimension ENUM('education_affiliation', 'professional_domain', 'causes_values', 'lifestyle', 'hobbies_passions', 'relationship_intent', 'personality_working_style', 'geography_mobility') NOT NULL,
    category_path VARCHAR(500) NULL,
    display_name_en VARCHAR(300) NOT NULL,
    display_name_lg VARCHAR(300) NULL,
    display_name_sw VARCHAR(300) NULL,
    aliases JSON NULL,
    popularity INT DEFAULT 0,
    is_sensitive TINYINT(1) DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_lu_interest_tags_dimension (dimension),
    INDEX idx_lu_interest_tags_slug (slug)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS lu_interest_profiles (
    id VARCHAR(36) PRIMARY KEY,
    account_id VARCHAR(36) NOT NULL,
    tag_id VARCHAR(36) NOT NULL,
    weight DECIMAL(5,4) DEFAULT 0.5000,
    mode ENUM('professional', 'dating', 'both') DEFAULT 'both',
    pinned TINYINT(1) DEFAULT 0,
    source ENUM('explicit', 'inferred', 'behavioral') DEFAULT 'explicit',
    last_signaled TIMESTAMP NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_lu_interest_profile (account_id, tag_id),
    FOREIGN KEY (account_id) REFERENCES lu_accounts(id) ON DELETE CASCADE,
    FOREIGN KEY (tag_id) REFERENCES lu_interest_tags(id) ON DELETE CASCADE,
    INDEX idx_lu_interest_profiles_account (account_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ─── Links (Professional Connections) ────────────────────────

CREATE TABLE IF NOT EXISTS lu_links (
    id VARCHAR(36) PRIMARY KEY,
    requester_id VARCHAR(36) NOT NULL,
    addressee_id VARCHAR(36) NOT NULL,
    status ENUM('requested', 'accepted', 'declined', 'blocked') DEFAULT 'requested',
    note VARCHAR(1000) NULL,
    strength_score DECIMAL(5,4) DEFAULT 0.0000,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_lu_link_pair (requester_id, addressee_id),
    FOREIGN KEY (requester_id) REFERENCES lu_accounts(id) ON DELETE CASCADE,
    FOREIGN KEY (addressee_id) REFERENCES lu_accounts(id) ON DELETE CASCADE,
    INDEX idx_lu_links_requester (requester_id),
    INDEX idx_lu_links_addressee (addressee_id),
    INDEX idx_lu_links_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ─── Sparks (Dating Actions) ─────────────────────────────────

CREATE TABLE IF NOT EXISTS lu_sparks (
    id VARCHAR(36) PRIMARY KEY,
    actor_id VARCHAR(36) NOT NULL,
    target_id VARCHAR(36) NOT NULL,
    action ENUM('spark_up', 'pass', 'standout', 'undo') NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_lu_spark_pair (actor_id, target_id),
    FOREIGN KEY (actor_id) REFERENCES lu_accounts(id) ON DELETE CASCADE,
    FOREIGN KEY (target_id) REFERENCES lu_accounts(id) ON DELETE CASCADE,
    INDEX idx_lu_sparks_actor (actor_id),
    INDEX idx_lu_sparks_target (target_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS lu_matches (
    id VARCHAR(36) PRIMARY KEY,
    account_a_id VARCHAR(36) NOT NULL,
    account_b_id VARCHAR(36) NOT NULL,
    spark_a_id VARCHAR(36) NULL,
    spark_b_id VARCHAR(36) NULL,
    thread_id VARCHAR(36) NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_lu_match_pair (account_a_id, account_b_id),
    FOREIGN KEY (account_a_id) REFERENCES lu_accounts(id) ON DELETE CASCADE,
    FOREIGN KEY (account_b_id) REFERENCES lu_accounts(id) ON DELETE CASCADE,
    INDEX idx_lu_matches_a (account_a_id),
    INDEX idx_lu_matches_b (account_b_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ─── Hubs (Communities) ──────────────────────────────────────

CREATE TABLE IF NOT EXISTS lu_hubs (
    id VARCHAR(36) PRIMARY KEY,
    slug VARCHAR(200) UNIQUE NOT NULL,
    name VARCHAR(300) NOT NULL,
    description TEXT NULL,
    type ENUM('alumni', 'professional', 'geographic', 'interest') DEFAULT 'professional',
    institution_id VARCHAR(36) NULL,
    cover_image VARCHAR(500) NULL,
    member_count INT DEFAULT 0,
    created_by VARCHAR(36) NOT NULL,
    is_public TINYINT(1) DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (institution_id) REFERENCES lu_institutions(id) ON DELETE SET NULL,
    FOREIGN KEY (created_by) REFERENCES lu_accounts(id) ON DELETE CASCADE,
    INDEX idx_lu_hubs_type (type),
    INDEX idx_lu_hubs_public (is_public)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS lu_hub_memberships (
    id VARCHAR(36) PRIMARY KEY,
    hub_id VARCHAR(36) NOT NULL,
    account_id VARCHAR(36) NOT NULL,
    role ENUM('member', 'moderator', 'admin') DEFAULT 'member',
    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_lu_hub_membership (hub_id, account_id),
    FOREIGN KEY (hub_id) REFERENCES lu_hubs(id) ON DELETE CASCADE,
    FOREIGN KEY (account_id) REFERENCES lu_accounts(id) ON DELETE CASCADE,
    INDEX idx_lu_hub_memberships_hub (hub_id),
    INDEX idx_lu_hub_memberships_account (account_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS lu_hub_posts (
    id VARCHAR(36) PRIMARY KEY,
    hub_id VARCHAR(36) NOT NULL,
    account_id VARCHAR(36) NOT NULL,
    content TEXT NOT NULL,
    media JSON NULL,
    like_count INT DEFAULT 0,
    comment_count INT DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP NULL,
    FOREIGN KEY (hub_id) REFERENCES lu_hubs(id) ON DELETE CASCADE,
    FOREIGN KEY (account_id) REFERENCES lu_accounts(id) ON DELETE CASCADE,
    INDEX idx_lu_hub_posts_hub (hub_id),
    INDEX idx_lu_hub_posts_account (account_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ─── Chat ─────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS lu_threads (
    id VARCHAR(36) PRIMARY KEY,
    type ENUM('direct', 'group', 'hub', 'spark') DEFAULT 'direct',
    mode ENUM('professional', 'dating') DEFAULT 'professional',
    created_by VARCHAR(36) NOT NULL,
    hub_id VARCHAR(36) NULL,
    title VARCHAR(300) NULL,
    last_message_at TIMESTAMP NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (created_by) REFERENCES lu_accounts(id) ON DELETE CASCADE,
    FOREIGN KEY (hub_id) REFERENCES lu_hubs(id) ON DELETE SET NULL,
    INDEX idx_lu_threads_mode (mode),
    INDEX idx_lu_threads_type (type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS lu_thread_participants (
    id VARCHAR(36) PRIMARY KEY,
    thread_id VARCHAR(36) NOT NULL,
    account_id VARCHAR(36) NOT NULL,
    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_read_at TIMESTAMP NULL,
    UNIQUE KEY uq_lu_thread_participant (thread_id, account_id),
    FOREIGN KEY (thread_id) REFERENCES lu_threads(id) ON DELETE CASCADE,
    FOREIGN KEY (account_id) REFERENCES lu_accounts(id) ON DELETE CASCADE,
    INDEX idx_lu_thread_participants_thread (thread_id),
    INDEX idx_lu_thread_participants_account (account_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS lu_messages (
    id VARCHAR(36) PRIMARY KEY,
    thread_id VARCHAR(36) NOT NULL,
    sender_id VARCHAR(36) NOT NULL,
    body TEXT NULL,
    type ENUM('text', 'image', 'voice_note', 'file', 'system') DEFAULT 'text',
    media JSON NULL,
    status ENUM('sent', 'delivered', 'read') DEFAULT 'sent',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP NULL,
    FOREIGN KEY (thread_id) REFERENCES lu_threads(id) ON DELETE CASCADE,
    FOREIGN KEY (sender_id) REFERENCES lu_accounts(id) ON DELETE CASCADE,
    INDEX idx_lu_messages_thread (thread_id),
    INDEX idx_lu_messages_sender (sender_id),
    INDEX idx_lu_messages_created (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ─── Jobs ────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS lu_jobs (
    id VARCHAR(36) PRIMARY KEY,
    org_id VARCHAR(36) NULL,
    org_name VARCHAR(300) NULL,
    posted_by VARCHAR(36) NOT NULL,
    title VARCHAR(300) NOT NULL,
    description TEXT NULL,
    location_id VARCHAR(36) NULL,
    location_text VARCHAR(300) NULL,
    employment_type ENUM('full_time', 'part_time', 'contract', 'internship', 'volunteer') DEFAULT 'full_time',
    seniority ENUM('student', 'entry', 'mid', 'senior', 'lead', 'executive', 'founder') DEFAULT 'entry',
    salary_min DECIMAL(12,2) NULL,
    salary_max DECIMAL(12,2) NULL,
    currency VARCHAR(10) DEFAULT 'UGX',
    skills JSON NULL,
    is_open TINYINT(1) DEFAULT 1,
    referral_open TINYINT(1) DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NULL,
    FOREIGN KEY (org_id) REFERENCES lu_orgs(id) ON DELETE SET NULL,
    FOREIGN KEY (posted_by) REFERENCES lu_accounts(id) ON DELETE CASCADE,
    FOREIGN KEY (location_id) REFERENCES lu_locations(id) ON DELETE SET NULL,
    INDEX idx_lu_jobs_open (is_open),
    INDEX idx_lu_jobs_posted_by (posted_by),
    INDEX idx_lu_jobs_employment_type (employment_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS lu_applications (
    id VARCHAR(36) PRIMARY KEY,
    job_id VARCHAR(36) NOT NULL,
    applicant_id VARCHAR(36) NOT NULL,
    cover_note TEXT NULL,
    status ENUM('applied', 'reviewed', 'shortlisted', 'rejected', 'hired') DEFAULT 'applied',
    referred_by VARCHAR(36) NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_lu_application (job_id, applicant_id),
    FOREIGN KEY (job_id) REFERENCES lu_jobs(id) ON DELETE CASCADE,
    FOREIGN KEY (applicant_id) REFERENCES lu_accounts(id) ON DELETE CASCADE,
    INDEX idx_lu_applications_job (job_id),
    INDEX idx_lu_applications_applicant (applicant_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS lu_saved_jobs (
    id VARCHAR(36) PRIMARY KEY,
    job_id VARCHAR(36) NOT NULL,
    account_id VARCHAR(36) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_lu_saved_job (job_id, account_id),
    FOREIGN KEY (job_id) REFERENCES lu_jobs(id) ON DELETE CASCADE,
    FOREIGN KEY (account_id) REFERENCES lu_accounts(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ─── Events ──────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS lu_events (
    id VARCHAR(36) PRIMARY KEY,
    org_id VARCHAR(36) NULL,
    created_by VARCHAR(36) NOT NULL,
    title VARCHAR(300) NOT NULL,
    description TEXT NULL,
    event_type ENUM('networking', 'workshop', 'conference', 'social', 'webinar', 'other') DEFAULT 'networking',
    start_at TIMESTAMP NOT NULL,
    end_at TIMESTAMP NULL,
    location_text VARCHAR(500) NULL,
    is_online TINYINT(1) DEFAULT 0,
    link VARCHAR(500) NULL,
    cover_image VARCHAR(500) NULL,
    max_attendees INT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (org_id) REFERENCES lu_orgs(id) ON DELETE SET NULL,
    FOREIGN KEY (created_by) REFERENCES lu_accounts(id) ON DELETE CASCADE,
    INDEX idx_lu_events_start (start_at),
    INDEX idx_lu_events_created_by (created_by)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS lu_event_rsvps (
    id VARCHAR(36) PRIMARY KEY,
    event_id VARCHAR(36) NOT NULL,
    account_id VARCHAR(36) NOT NULL,
    status ENUM('going', 'maybe', 'not_going') DEFAULT 'going',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_lu_event_rsvp (event_id, account_id),
    FOREIGN KEY (event_id) REFERENCES lu_events(id) ON DELETE CASCADE,
    FOREIGN KEY (account_id) REFERENCES lu_accounts(id) ON DELETE CASCADE,
    INDEX idx_lu_event_rsvps_event (event_id),
    INDEX idx_lu_event_rsvps_account (account_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ─── Notifications ───────────────────────────────────────────

CREATE TABLE IF NOT EXISTS lu_notifications (
    id VARCHAR(36) PRIMARY KEY,
    account_id VARCHAR(36) NOT NULL,
    type VARCHAR(100) NOT NULL,
    title VARCHAR(300) NOT NULL,
    body TEXT NULL,
    data JSON NULL,
    is_read TINYINT(1) DEFAULT 0,
    action_url VARCHAR(500) NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (account_id) REFERENCES lu_accounts(id) ON DELETE CASCADE,
    INDEX idx_lu_notifications_account (account_id),
    INDEX idx_lu_notifications_read (is_read)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ─── Safety ──────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS lu_reports (
    id VARCHAR(36) PRIMARY KEY,
    reporter_id VARCHAR(36) NOT NULL,
    target_account_id VARCHAR(36) NOT NULL,
    target_content_type VARCHAR(100) NULL,
    target_content_id VARCHAR(36) NULL,
    reason ENUM('spam', 'harassment', 'fake_profile', 'inappropriate_content', 'scam', 'other') DEFAULT 'other',
    detail TEXT NULL,
    status ENUM('pending', 'reviewed', 'actioned', 'dismissed') DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (reporter_id) REFERENCES lu_accounts(id) ON DELETE CASCADE,
    FOREIGN KEY (target_account_id) REFERENCES lu_accounts(id) ON DELETE CASCADE,
    INDEX idx_lu_reports_reporter (reporter_id),
    INDEX idx_lu_reports_target (target_account_id),
    INDEX idx_lu_reports_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS lu_blocks (
    id VARCHAR(36) PRIMARY KEY,
    blocker_id VARCHAR(36) NOT NULL,
    blocked_id VARCHAR(36) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_lu_block (blocker_id, blocked_id),
    FOREIGN KEY (blocker_id) REFERENCES lu_accounts(id) ON DELETE CASCADE,
    FOREIGN KEY (blocked_id) REFERENCES lu_accounts(id) ON DELETE CASCADE,
    INDEX idx_lu_blocks_blocker (blocker_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ─── Verification ────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS lu_verifications (
    id VARCHAR(36) PRIMARY KEY,
    account_id VARCHAR(36) NOT NULL,
    type ENUM('phone', 'email', 'id_card', 'passport', 'degree', 'employment') DEFAULT 'phone',
    status ENUM('pending', 'approved', 'rejected', 'expired') DEFAULT 'pending',
    metadata JSON NULL,
    verified_at TIMESTAMP NULL,
    expires_at TIMESTAMP NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (account_id) REFERENCES lu_accounts(id) ON DELETE CASCADE,
    INDEX idx_lu_verifications_account (account_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

SET foreign_key_checks = 1;
