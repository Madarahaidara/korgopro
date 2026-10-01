"""Recharge le cache de schéma de PostgREST (Supabase).

POURQUOI : PostgREST garde en mémoire la liste des tables et des FONCTIONS
exposées par l'API REST. Une RPC créée après le dernier rechargement reste
invisible et le téléphone reçoit :

    Could not find the function public.app_create_sale(...) in the schema
    cache          (code PGRST202)

Supabase recharge normalement le cache sur événement DDL, mais un
rechargement explicite lève tout doute (surtout si la fonction a été créée via
un accès direct à la base, hors des outils du dashboard).

Usage : python _reload_postgrest_cache.py
"""
import os
import time

from dotenv import load_dotenv
from sqlalchemy import create_engine, text


def main() -> int:
    load_dotenv(".env")
    url = os.environ["DATABASE_URL"].replace("postgresql://",
                                             "postgresql+psycopg2://")
    engine = create_engine(url, connect_args={"sslmode": "require"})
    with engine.begin() as c:
        c.execute(text("NOTIFY pgrst, 'reload schema'"))
    # Le rechargement est asynchrone : on laisse PostgREST le traiter.
    time.sleep(2)
    print("NOTIFY pgrst, 'reload schema' envoye : cache de schema recharge.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
