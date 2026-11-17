try:
    import asyncpg
except ImportError:  # permits health/read-only unit tests without the optional DB driver installed
    asyncpg = None
from fastapi import HTTPException
_pool = None
_ingest_pool = None
_platform_admin_pool = None

async def open_pool(database_url: str, ingest_database_url: str = "", platform_admin_database_url: str = ""):
    global _pool, _ingest_pool, _platform_admin_pool
    if (database_url or ingest_database_url or platform_admin_database_url) and asyncpg is None:
        raise RuntimeError("Le pilote PostgreSQL asyncpg est requis pour ouvrir les pools de base de données.")
    if database_url:
        _pool = await asyncpg.create_pool(database_url, min_size=1, max_size=10, command_timeout=10)
    if ingest_database_url:
        _ingest_pool = await asyncpg.create_pool(ingest_database_url, min_size=1, max_size=3, command_timeout=30)
    if platform_admin_database_url:
        _platform_admin_pool = await asyncpg.create_pool(platform_admin_database_url, min_size=1, max_size=3, command_timeout=10)

async def close_pool():
    global _pool, _ingest_pool, _platform_admin_pool
    if _platform_admin_pool:
        await _platform_admin_pool.close()
        _platform_admin_pool = None
    if _ingest_pool:
        await _ingest_pool.close()
        _ingest_pool = None
    if _pool:
        await _pool.close()
        _pool = None

def get_pool():
    if _pool is None:
        raise HTTPException(503, "Base de données non configurée.")
    return _pool

def get_corpus_ingest_pool():
    if _ingest_pool is None:
        raise HTTPException(503, "Connexion d'ingestion du corpus juridique non configurée.")
    return _ingest_pool


def get_platform_admin_pool():
    if _platform_admin_pool is None:
        raise HTTPException(503, "Connexion PostgreSQL administrateur non configurée.")
    return _platform_admin_pool
