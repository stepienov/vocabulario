"""One-shot prod diagnosis. Do not print secrets."""
from datetime import datetime, timezone, timedelta
from urllib.parse import urlparse

import psycopg2
from dotenv import dotenv_values

env = dotenv_values(".env")
url = env["PROD_DATABASE_URL"]
p = urlparse(url)
conn = psycopg2.connect(
    host=p.hostname,
    port=p.port,
    user=p.username,
    password=p.password,
    dbname=p.path.lstrip("/"),
)
conn.autocommit = True
cur = conn.cursor()

print("NOW_UTC", datetime.now(timezone.utc).isoformat())

print("\n=== users ===")
cur.execute("SELECT email FROM users ORDER BY email")
for r in cur.fetchall():
    print(" ", r[0])

print("\n=== cards by email / enrichment_status (live) ===")
cur.execute(
    """
    SELECT u.email, lc.enrichment_status, count(*)
    FROM learning_cards lc
    JOIN users u ON u.id = lc.user_id
    WHERE lc.deleted_at IS NULL
    GROUP BY 1, 2
    ORDER BY 1, 2
    """
)
for r in cur.fetchall():
    print(" ", r)

print("\n=== nowy4 non-ready cards ===")
cur.execute(
    """
    SELECT lc.lemma_l2, lc.pos, lc.enrichment_status, lc.enrichment_error,
           lc.created_at, lc.updated_at,
           (lc.lexical_entry_id IS NOT NULL) AS has_lex,
           lc.import_job_id::text
    FROM learning_cards lc
    JOIN users u ON u.id = lc.user_id
    WHERE u.email = 'nowy4@test.com'
      AND lc.deleted_at IS NULL
      AND lc.enrichment_status <> 'ready'
    ORDER BY lc.updated_at DESC
    """
)
rows = cur.fetchall()
print(" count", len(rows))
for r in rows:
    print(" ", r)

print("\n=== nowy4 pending updated_at spread ===")
cur.execute(
    """
    SELECT min(lc.updated_at), max(lc.updated_at), min(lc.created_at), max(lc.created_at)
    FROM learning_cards lc
    JOIN users u ON u.id = lc.user_id
    WHERE u.email = 'nowy4@test.com'
      AND lc.deleted_at IS NULL
      AND lc.enrichment_status = 'pending'
    """
)
print(" ", cur.fetchone())

print("\n=== nowy4 import jobs ===")
cur.execute(
    """
    SELECT column_name FROM information_schema.columns
    WHERE table_name = 'import_jobs' ORDER BY ordinal_position
    """
)
print(" cols", [r[0] for r in cur.fetchall()])

cur.execute(
    """
    SELECT ij.id::text, ij.status, ij.created_at, ij.updated_at
    FROM import_jobs ij
    JOIN users u ON u.id = ij.user_id
    WHERE u.email = 'nowy4@test.com'
    ORDER BY ij.created_at DESC
    LIMIT 8
    """
)
print(" jobs", cur.fetchall())

print("\n=== llm_call last 3h ===")
cur.execute(
    """
    SELECT date_trunc('minute', created_at) AS minute,
           status, count(*),
           round(avg(duration_ms)) AS avg_ms,
           max(duration_ms) AS max_ms
    FROM app_logs
    WHERE category = 'llm'
      AND created_at > now() - interval '3 hours'
    GROUP BY 1, 2
    ORDER BY 1 DESC
    LIMIT 40
    """
)
llm_min = cur.fetchall()
print(" buckets", len(llm_min))
for r in llm_min:
    print(" ", r)

print("\n=== llm_call last 30 min totals ===")
cur.execute(
    """
    SELECT status, count(*), coalesce(sum(duration_ms),0), max(created_at)
    FROM app_logs
    WHERE category = 'llm'
      AND created_at > now() - interval '30 minutes'
    GROUP BY status
    """
)
print(" ", cur.fetchall())

print("\n=== last 15 llm_call rows ===")
cur.execute(
    """
    SELECT created_at, status, duration_ms, message, user_id::text, entity_id, payload
    FROM app_logs
    WHERE category = 'llm'
    ORDER BY created_at DESC
    LIMIT 15
    """
)
for r in cur.fetchall():
    print(" ", r[0], r[1], r[2], r[3], "user", r[4], "entity", r[5], "payload", r[6])

print("\n=== enrichment_failed last 3h ===")
cur.execute(
    """
    SELECT created_at, status, message, entity_id, error_message
    FROM app_logs
    WHERE event = 'enrichment_failed'
      AND created_at > now() - interval '3 hours'
    ORDER BY created_at DESC
    LIMIT 20
    """
)
ef = cur.fetchall()
print(" count", len(ef))
for r in ef:
    print(" ", r)

print("\n=== http GET lists/cards last 15 min (phone poll?) ===")
cur.execute(
    """
    SELECT http_path, count(*)
    FROM app_logs
    WHERE category = 'http'
      AND created_at > now() - interval '15 minutes'
    GROUP BY 1
    ORDER BY 2 DESC
    LIMIT 20
    """
)
print(" paths", cur.fetchall())

print("\n=== app_logs categories last 30 min ===")
cur.execute(
    """
    SELECT category, event, status, count(*)
    FROM app_logs
    WHERE created_at > now() - interval '30 minutes'
    GROUP BY 1,2,3
    ORDER BY 4 DESC
    LIMIT 30
    """
)
for r in cur.fetchall():
    print(" ", r)

cur.close()
conn.close()
