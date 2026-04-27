import os
import psycopg2
import psycopg2.extras
from pathlib import Path


def _get_conn():
    return psycopg2.connect(os.environ["DATABASE_URL"])


def init_db():
    schema = (Path(__file__).parent / "schema.sql").read_text()
    with _get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(schema)
        conn.commit()


def insert_raw_item(source, external_id, url, title, content=None, source_score=None):
    """Insert a raw item. Returns the row id whether newly inserted or already existing."""
    sql = """
        INSERT INTO raw_items (source, external_id, url, title, content, source_score)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (source, external_id) DO NOTHING
        RETURNING id
    """
    with _get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (source, external_id, url, title, content, source_score))
            row = cur.fetchone()
            if row is None:
                # Already existed — fetch the existing id
                cur.execute(
                    "SELECT id FROM raw_items WHERE source = %s AND external_id = %s",
                    (source, external_id),
                )
                row = cur.fetchone()
        conn.commit()
    return row[0] if row else None


def get_raw_items_in_window(window_start, window_end):
    """Return all raw_items fetched within [window_start, window_end]."""
    sql = """
        SELECT id, source, external_id, url, title, content, source_score, fetched_at
        FROM raw_items
        WHERE fetched_at >= %s AND fetched_at < %s
        ORDER BY fetched_at
    """
    with _get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (window_start, window_end))
            return cur.fetchall()


def get_recently_published_raw_ids(limit_digests=2):
    """Return the set of raw_item_ids already included in the N most recent digests."""
    sql = """
        SELECT DISTINCT si.raw_item_id
        FROM digest_items di
        JOIN scored_items si ON si.id = di.scored_item_id
        WHERE di.digest_id IN (
            SELECT id FROM digests ORDER BY created_at DESC LIMIT %s
        )
    """
    with _get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (limit_digests,))
            return {row[0] for row in cur.fetchall()}


def insert_scored_item(raw_item_id, one_liner, full_summary, importance, dedup_group=None):
    """Insert a scored item. Returns the new row id."""
    sql = """
        INSERT INTO scored_items (raw_item_id, one_liner, full_summary, importance, dedup_group)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id
    """
    with _get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (raw_item_id, one_liner, full_summary, importance, dedup_group))
            row_id = cur.fetchone()[0]
        conn.commit()
    return row_id


def create_digest(slug, window_start, window_end, scored_item_ids):
    """Create a digest record and populate digest_items. Returns the digest id.
    If a digest with this slug already exists, returns its id without re-inserting."""
    with _get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO digests (slug, window_start, window_end, item_count)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (slug) DO UPDATE
                    SET item_count = EXCLUDED.item_count
                RETURNING id
                """,
                (slug, window_start, window_end, len(scored_item_ids)),
            )
            digest_id = cur.fetchone()[0]
            # Clear and re-insert digest_items so re-runs stay consistent
            cur.execute("DELETE FROM digest_items WHERE digest_id = %s", (digest_id,))
            psycopg2.extras.execute_values(
                cur,
                "INSERT INTO digest_items (digest_id, scored_item_id, position) VALUES %s",
                [(digest_id, sid, pos + 1) for pos, sid in enumerate(scored_item_ids)],
            )
        conn.commit()
    return digest_id


def get_digest_by_slug(slug):
    """Return digest metadata + ordered items for HTML generation."""
    with _get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM digests WHERE slug = %s", (slug,))
            digest = cur.fetchone()
            if not digest:
                return None
            cur.execute(
                """
                SELECT si.*, ri.source, ri.url, ri.title AS raw_title, di.position
                FROM digest_items di
                JOIN scored_items si ON si.id = di.scored_item_id
                JOIN raw_items ri ON ri.id = si.raw_item_id
                WHERE di.digest_id = %s
                ORDER BY di.position
                """,
                (digest["id"],),
            )
            items = cur.fetchall()
    return {"digest": digest, "items": items}


def get_recent_digests(limit=20):
    """Return the most recent digests for the index page."""
    sql = """
        SELECT id, slug, window_start, window_end, item_count, created_at
        FROM digests
        ORDER BY created_at DESC
        LIMIT %s
    """
    with _get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (limit,))
            return cur.fetchall()


def mark_telegram_sent(digest_id):
    with _get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE digests SET telegram_sent = TRUE WHERE id = %s", (digest_id,))
        conn.commit()


def mark_html_generated(digest_id):
    with _get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE digests SET html_generated = TRUE WHERE id = %s", (digest_id,))
        conn.commit()
