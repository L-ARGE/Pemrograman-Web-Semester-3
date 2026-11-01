import os
import psycopg2
from dotenv import load_dotenv
from psycopg2.extras import RealDictCursor

# Muat variabel environment dari .env
load_dotenv()

def get_db_connection():
    """Membuka koneksi ke PostgreSQL menggunakan konfigurasi dari .env."""
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

def init_db(sql_filepath="schema_kasir.sql"):
    """Mengeksekusi file .sql untuk menginisialisasi tabel-tabel database."""
    with open(sql_filepath, "r", encoding="utf-8") as f:
        sql_commands = f.read()

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql_commands)
        conn.commit()
        print("Inisialisasi tabel kasir berhasil!")
    finally:
        conn.close()

# ==============================================================
# 1. OPERASI PRODUK (CRUD)
# ==============================================================

def get_all_products():
    """Mengambil seluruh data produk."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM products ORDER BY id ASC;")
            return cur.fetchall()
    finally:
        conn.close()

def add_product(name: str, price: float, stock: int):
    """Menambahkan produk baru."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO products (name, price, stock)
                VALUES (%s, %s, %s)
                RETURNING id;
                """,
                (name, price, stock),
            )
            new_id = cur.fetchone()["id"]
        conn.commit()
        return new_id
    finally:
        conn.close()

def update_product_stock(product_id: int, new_stock: int):
    """Memperbarui stok produk."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE products SET stock = %s WHERE id = %s;",
                (new_stock, product_id),
            )
        conn.commit()
    finally:
        conn.close()

# ==============================================================
# 2. OPERASI TRANSAKSI PENJUALAN (ACID Transaction)
# ==============================================================

def create_order(customer_name: str, items: list[dict]):
    """
    Membuat transaksi pesanan baru secara atomis (Transaction).
    Format items: [{'product_id': 1, 'quantity': 2, 'unit_price': 18000}, ...]
    
    Jika stok kurang atau ada error, transaksi otomatis di-ROLLBACK.
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # 1. Insert header pesanan & dapatkan id order
            cur.execute(
                """
                INSERT INTO orders (customer_name, status)
                VALUES (%s, 'paid')
                RETURNING id;
                """,
                (customer_name,),
            )
            order_id = cur.fetchone()["id"]

            # 2. Loop setiap item pesanan
            for item in items:
                p_id = item["product_id"]
                qty = item["quantity"]
                price = item["unit_price"]

                # Validasi & kurangi stok produk
                cur.execute(
                    "UPDATE products SET stock = stock - %s WHERE id = %s AND stock >= %s RETURNING id;",
                    (qty, p_id, qty),
                )
                if not cur.fetchone():
                    raise ValueError(f"Stok produk ID {p_id} tidak mencukupi atau produk tidak ditemukan.")

                # Insert ke tabel order_items
                cur.execute(
                    """
                    INSERT INTO order_items (order_id, product_id, quantity, unit_price)
                    VALUES (%s, %s, %s, %s);
                    """,
                    (order_id, p_id, qty, price),
                )

        # Jika semua loop berhasil tanpa error, COMMIT perubahan
        conn.commit()
        return order_id

    except Exception as e:
        conn.rollback()  # Batalkan semua perubahan jika terjadi kegagalan
        raise e
    finally:
        conn.close()

# ==============================================================
# 3. PELAPORAN & DETAIL TRANSAKSI (JOIN & AGGREGATE)
# ==============================================================

def get_all_orders_summary():
    """
    Mengambil ringkasan semua order beserta total harga belanja (menggunakan JOIN & SUM).
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            query = """
                SELECT 
                    o.id AS order_id,
                    o.customer_name,
                    o.status,
                    o.order_date,
                    COALESCE(SUM(oi.quantity * oi.unit_price), 0) AS total_amount,
                    COALESCE(SUM(oi.quantity), 0) AS total_items
                FROM orders o
                LEFT JOIN order_items oi ON o.id = oi.order_id
                GROUP BY o.id, o.customer_name, o.status, o.order_date
                ORDER BY o.order_date DESC;
            """
            cur.execute(query)
            return cur.fetchall()
    finally:
        conn.close()

def get_order_details(order_id: int):
    """
    Mengambil nota detail dari suatu order dengan Multi-Table JOIN (orders -> order_items -> products).
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # Info header pesanan
            cur.execute("SELECT * FROM orders WHERE id = %s;", (order_id,))
            order = cur.fetchone()
            if not order:
                return None

            # Rincian item barang pesanan
            query_items = """
                SELECT 
                    oi.id AS item_id,
                    p.name AS product_name,
                    oi.quantity,
                    oi.unit_price,
                    (oi.quantity * oi.unit_price) AS subtotal
                FROM order_items oi
                JOIN products p ON oi.product_id = p.id
                WHERE oi.order_id = %s
                ORDER BY oi.id ASC;
            """
            cur.execute(query_items, (order_id,))
            order["items"] = cur.fetchall()
            order["total_price"] = sum(item["subtotal"] for item in order["items"])

            return order
    finally:
        conn.close()

def update_order_status(order_id: int, new_status: str):
    """Mengubah status pesanan ('pending', 'paid', 'cancelled')."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE orders SET status = %s WHERE id = %s;",
                (new_status, order_id),
            )
        conn.commit()
    finally:
        conn.close()

def delete_order(order_id: int):
    """Menghapus order (order_items akan otomatis terhapus karena ON DELETE CASCADE)."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM orders WHERE id = %s;", (order_id,))
        conn.commit()
    finally:
        conn.close()
