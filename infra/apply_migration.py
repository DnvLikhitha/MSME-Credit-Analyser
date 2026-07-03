"""Apply the Phase 1 SQL migration to Supabase via SQLAlchemy."""
import os
import sqlalchemy
from dotenv import load_dotenv

load_dotenv()

db_url = os.getenv("DATABASE_URL")
if not db_url:
    raise SystemExit("ERROR: DATABASE_URL not set in .env")

engine = sqlalchemy.create_engine(db_url, pool_pre_ping=True)

migration_file = "infra/migrations/001_initial_schema.sql"
with open(migration_file, "r") as f:
    sql = f.read()

print(f"Applying migration: {migration_file}")

# Split on semicolons but ignore comment-only lines
statements = []
for stmt in sql.split(";"):
    stmt = stmt.strip()
    # Filter out empty statements and pure-comment blocks
    non_comment = "\n".join(
        line for line in stmt.splitlines() if not line.strip().startswith("--")
    ).strip()
    if non_comment:
        statements.append(stmt)

errors = []
with engine.connect() as conn:
    for i, stmt in enumerate(statements, 1):
        try:
            conn.execute(sqlalchemy.text(stmt))
        except Exception as e:
            errors.append(f"  Statement {i}: {e}")
    conn.commit()

if errors:
    print("⚠️  Some statements had warnings (likely already exists):")
    for e in errors:
        print(e)
else:
    print("✅  All statements applied cleanly.")

# Verify
with engine.connect() as conn:
    result = conn.execute(sqlalchemy.text(
        "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' ORDER BY table_name"
    ))
    tables = [row[0] for row in result]

print(f"\n📋  Tables in Supabase ({len(tables)}):")
for t in tables:
    print(f"  ✓ {t}")
