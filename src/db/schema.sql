-- Raw fetched items before processing
CREATE TABLE IF NOT EXISTS raw_items (
    id              SERIAL PRIMARY KEY,
    source          TEXT NOT NULL,              -- 'arxiv', 'reddit:MachineLearning', 'hn', 'rss:techcrunch'
    external_id     TEXT NOT NULL,              -- Source-specific ID (arxiv ID, reddit post ID, etc.)
    url             TEXT NOT NULL,
    title           TEXT NOT NULL,
    content         TEXT,                       -- Abstract, self-text, or article snippet
    source_score    DOUBLE PRECISION,           -- Upvotes, HN points, etc. (NULL for RSS/arXiv)
    fetched_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(source, external_id)                 -- Prevent re-inserting same item
);

-- Processed and scored items
CREATE TABLE IF NOT EXISTS scored_items (
    id              SERIAL PRIMARY KEY,
    raw_item_id     INTEGER NOT NULL REFERENCES raw_items(id),
    one_liner       TEXT NOT NULL,              -- One-line summary for Telegram
    full_summary    TEXT NOT NULL,              -- 3-5 sentence summary for web page
    importance      INTEGER NOT NULL CHECK(importance BETWEEN 1 AND 10),
    dedup_group     TEXT,                       -- Group ID for deduped items (same story, multiple sources)
    scored_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Generated digests
CREATE TABLE IF NOT EXISTS digests (
    id              SERIAL PRIMARY KEY,
    slug            TEXT NOT NULL UNIQUE,       -- '2026-04-13-morning' or '2026-04-13-evening'
    window_start    TIMESTAMPTZ NOT NULL,       -- Start of this digest's time window
    window_end      TIMESTAMPTZ NOT NULL,       -- End of this digest's time window
    item_count      INTEGER NOT NULL,
    telegram_sent   BOOLEAN NOT NULL DEFAULT FALSE,
    html_generated  BOOLEAN NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Junction: which scored items are in which digest
CREATE TABLE IF NOT EXISTS digest_items (
    digest_id       INTEGER NOT NULL REFERENCES digests(id),
    scored_item_id  INTEGER NOT NULL REFERENCES scored_items(id),
    position        INTEGER NOT NULL,           -- Order in the digest (1 = most important)
    PRIMARY KEY (digest_id, scored_item_id)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_raw_items_fetched ON raw_items(fetched_at);
CREATE INDEX IF NOT EXISTS idx_raw_items_source ON raw_items(source);
CREATE INDEX IF NOT EXISTS idx_scored_items_importance ON scored_items(importance DESC);
CREATE INDEX IF NOT EXISTS idx_digests_slug ON digests(slug);
