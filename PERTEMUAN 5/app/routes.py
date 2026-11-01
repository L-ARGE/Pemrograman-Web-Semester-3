from flask import Blueprint, jsonify, render_template, request
import mysql.connector
from config import DB_CONFIG

api_bp = Blueprint("api", __name__)


def get_db():
  return mysql.connector.connect(**DB_CONFIG)


def barang_json(row):
  data = dict(row)
  data["harga"] = float(data["harga"])
  return data


@api_bp.route("/")
def index():
  return render_template("index.html")


# Mengambil semua barang yang ada di database
@api_bp.route("/api/barang", methods=["GET"])
def get_barang():
  conn = get_db()
  cursor = None
  try:
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM barang ORDER BY id")
    rows = cursor.fetchall()  # <-- DIPERBAIKI: Mengambil data hasil query
  finally:
    if cursor is not None:
      cursor.close()
    conn.close()
  return jsonify([barang_json(row) for row in rows])


# Menambahkan barang
@api_bp.route("/api/barang", methods=["POST"])
def create_barang():
  data = request.get_json(silent=True)

  # <-- DIPERBAIKI: Memastikan body berupa dictionary (JSON valid)
  if not isinstance(data, dict):
    return jsonify({"error": "Body harus berupa JSON"}), 400

  # <-- DIPERBAIKI: Mengambil nilai dari payload JSON
  nama = data.get("nama")
  harga = data.get("harga")
  stok = data.get("stok")

  if not isinstance(nama, str) or not nama.strip():
    return jsonify({"error": "Nama barang wajib diisi"}), 400

  try:
    harga = float(harga)
    stok = int(stok)

    if not 0 <= harga < float("inf") or stok < 0:
      raise ValueError
  except (ValueError, TypeError, OverflowError):
    return jsonify({"error": "Harga dan stok tidak valid"}), 400

  conn = get_db()  # <-- DIPERBAIKI: Menyimpan objek koneksi ke variabel conn
  cursor = None
  try:
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        """
            INSERT INTO barang (nama, harga, stok)
            VALUES (%s, %s, %s)
            """,
        (nama.strip(), harga, stok),
    )
    barang_id = cursor.lastrowid
    cursor.execute("SELECT * FROM barang WHERE id = %s", (barang_id,))
    row = cursor.fetchone()
    conn.commit()
  finally:
    if cursor is not None:
      cursor.close()
    conn.close()  # <-- DIPERBAIKI: Menutup koneksi database di blok finally

  return jsonify(barang_json(row)), 201


# Memperbarui barang berdasarkan ID
@api_bp.route("/api/barang/<int:id>", methods=["PUT"])
def update_barang(id):
  data = request.get_json(silent=True)

  if not isinstance(data, dict):
    return jsonify({"error": "Body harus berupa JSON"}), 400

  nama = data.get("nama")
  harga = data.get("harga")
  stok = data.get("stok")

  if not isinstance(nama, str) or not nama.strip():
    return jsonify({"error": "Nama barang wajib diisi"}), 400

  try: 
    harga = float(harga)
    stok = int(stok)

    if not 0 <= harga < float("inf") or stok < 0:
      raise ValueError
  except (ValueError, TypeError, OverflowError):
    return jsonify({"error": "Harga dan stok tidak valid"}), 400

  conn = get_db()
  cursor = None
  try:
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        """
            UPDATE barang
            SET nama = %s, harga = %s, stok = %s
            WHERE id = %s
            """,
        (nama.strip(), harga, stok, id),
    )
    cursor.execute("SELECT * FROM barang WHERE id = %s", (id,))
    row = cursor.fetchone()
    if row is not None:
      conn.commit()
  finally:
    if cursor is not None:
      cursor.close()
    conn.close()

  if row is None:
    return jsonify({"error": "Barang tidak ditemukan"}), 404

  return jsonify(barang_json(row))


# Menghapus barang berdasarkan ID
@api_bp.route("/api/barang/<int:id>", methods=["DELETE"])
def delete_barang(id):
  conn = get_db()
  cursor = None
  try:
    cursor = conn.cursor()
    cursor.execute("DELETE FROM barang WHERE id = %s", (id,))
    deleted = cursor.rowcount > 0
    if deleted:
      conn.commit()
  finally:
    if cursor is not None:
      cursor.close()
    conn.close()

  if not deleted:
    return jsonify({"error": "Barang tidak ditemukan"}), 404

  return jsonify({"message": "Barang berhasil dihapus"})