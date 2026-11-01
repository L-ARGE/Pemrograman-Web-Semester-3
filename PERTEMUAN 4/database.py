import os

import psycopg2
from dotenv import load_dotenv
from psycopg2.extras import RealDictCursor

load_dotenv()

def get_db_connection():
    """Membuat database baru bernama Perpustakaan"""
    password = os.getenv("PGPASSWORD")
    if not password:
        raise RuntimeError("PGPASSWORD belum diatur di file .env")
    
    return psycopg2.connect(
        host=os.environ.get("PGHOST", "localhost"),
        port=int(os.environ.get("PGPORT", "5432")),
        dbname=os.environ.get("PGDATABASE", "dB_Perpustakaan"),
        user=os.environ.get("PGUSER", "postgres"),
        password=password,
        cursor_factory=RealDictCursor,
    )