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

errors = []
with engine.connect() as conn:
    try:
        conn.execute(sqlalchemy.text(sql))
        conn.commit()
    except Exception as e:
        errors.append(str(e))
        conn.rollback()

if errors:
    print("[!] Error applying migration:")
    for e in errors:
        print(e)
else:
    print("[*] All statements applied cleanly.")

# Verify
with engine.connect() as conn:
    result = conn.execute(sqlalchemy.text(
        "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' ORDER BY table_name"
    ))
    tables = [row[0] for row in result]

print(f"\n[*] Tables in Database ({len(tables)}):")
for t in tables:
    print(f"  - {t}")
