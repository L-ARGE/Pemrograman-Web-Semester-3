-- ==============================================================
-- SKEMA DATABASE: Mini Kasir / Order Management (PostgreSQL)
-- File: schema_kasir.sql
-- ==============================================================

-- 1. Tabel Master Produk
CREATE TABLE IF NOT EXISTS products (
    id SERIAL PRIMARY KEY,
    name VARCHAR(150) NOT NULL,
    price NUMERIC(12, 2) NOT NULL CHECK (price >= 0),
    stock INT NOT NULL DEFAULT 0 CHECK (stock >= 0),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. Tabel Header Transaksi / Pesanan
CREATE TABLE IF NOT EXISTS orders (
    id SERIAL PRIMARY KEY,
    customer_name VARCHAR(100) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'paid' CHECK (status IN ('pending', 'paid', 'cancelled')),
    order_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 3. Tabel Detail Pesanan (Relasi Many-to-Many antara orders & products)
CREATE TABLE IF NOT EXISTS order_items (
    id SERIAL PRIMARY KEY,
    order_id INT NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    product_id INT NOT NULL REFERENCES products(id) ON DELETE RESTRICT,
    quantity INT NOT NULL CHECK (quantity > 0),
    unit_price NUMERIC(12, 2) NOT NULL CHECK (unit_price >= 0)
);

-- Index untuk mempercepat pencarian item berdasarkan order_id
CREATE INDEX IF NOT EXISTS idx_order_items_order_id ON order_items(order_id);

-- ==============================================================
-- DUMMY DATA UNTUK PENGUJIAN
-- ==============================================================

INSERT INTO products (name, price, stock) VALUES
('Kopi Susu Gula Aren', 18000.00, 50),
('Croissant Almond', 25000.00, 30),
('Matcha Latte', 22000.00, 40),
('Air Mineral 600ml', 5000.00, 100)
ON CONFLICT DO NOTHING;
