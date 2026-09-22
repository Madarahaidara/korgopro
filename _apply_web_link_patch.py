"""Applique supabase_web_link_patch.sql à la base Supabase (via DATABASE_URL).

Le script est idempotent et termine par une requête de vérification.

Usage : python _apply_web_link_patch.py
"""
import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

SQL_FILE = Path(__file__).with_name("supabase_web_link_patch.sql")


def split_sql(sql: str):
    """Découpe un script SQL en instructions (les blocs $$...$$ sont préservés)."""
    statements, buf, in_dollar = [], [], False
    i = 0
    while i < len(sql):
        if sql.startswith("$$", i):
            in_dollar = not in_dollar
            buf.append("$$")
            i += 2
            continue
        if sql[i] == ";" and not in_dollar:
            statements.append("".join(buf))
            buf = []
        else:
            buf.append(sql[i])
        i += 1
    if "".join(buf).strip():
        statements.append("".join(buf))
    return [s.strip() for s in statements if s.strip()]


def main():
    load_dotenv(".env")
    url = os.environ["DATABASE_URL"].replace("postgresql://", "postgresql+psycopg2://")
    engine = create_engine(url, connect_args={"sslmode": "require"})
    script = SQL_FILE.read_text(encoding="utf-8")

    with engine.begin() as c:
        for statement in split_sql(script):
            if all(line.strip().startswith("--") or not line.strip()
                   for line in statement.splitlines()):
                continue  # bloc de commentaires seul
            label = " ".join(statement.split())[:70]
            result = c.execute(text(statement))
            if result.returns_rows:
                print(f"OK (lecture) : {label}")
                for row in result.fetchall():
                    print("   ", row)
            else:
                print(f"OK : {label} ... ({result.rowcount} ligne(s) touchée(s))")
    print("\nPatch appliqué.")


if __name__ == "__main__":
    main()
