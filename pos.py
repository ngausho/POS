#!/usr/bin/env python3
"""Simple POS (Point of Sale) application backed by SQLite."""

from __future__ import annotations

import argparse
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class Product:
    id: int
    name: str
    price: float
    stock: int


class POSDatabase:
    def __init__(self, db_path: str = "pos.db") -> None:
        self.db_path = Path(db_path)
        self.connection = sqlite3.connect(self.db_path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self._init_schema()

    def _init_schema(self) -> None:
        cursor = self.connection.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                price REAL NOT NULL CHECK(price >= 0),
                stock INTEGER NOT NULL CHECK(stock >= 0),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS sales (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER NOT NULL,
                quantity INTEGER NOT NULL CHECK(quantity > 0),
                unit_price REAL NOT NULL CHECK(unit_price >= 0),
                total_amount REAL NOT NULL CHECK(total_amount >= 0),
                sold_at TEXT NOT NULL,
                FOREIGN KEY(product_id) REFERENCES products(id)
            )
            """
        )

        # Backwards compatible migration for already-existing databases.
        product_columns = {
            row["name"]
            for row in cursor.execute("PRAGMA table_info(products)").fetchall()
        }
        if "updated_at" not in product_columns:
            cursor.execute(
                "ALTER TABLE products ADD COLUMN updated_at TEXT NOT NULL DEFAULT ''"
            )
            cursor.execute(
                "UPDATE products SET updated_at = created_at WHERE updated_at = ''"
            )

        self.connection.commit()

    def close(self) -> None:
        self.connection.close()

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")

    def add_product(self, name: str, price: float, stock: int) -> int:
        now = self._now()
        cursor = self.connection.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO products (name, price, stock, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (name, price, stock, now, now),
            )
            self.connection.commit()
            return int(cursor.lastrowid)
        except sqlite3.IntegrityError as exc:
            if "UNIQUE constraint failed" in str(exc):
                raise ValueError(f"Product '{name}' already exists.") from exc
            raise

    def restock_product(self, product_id: int, quantity: int) -> None:
        cursor = self.connection.cursor()
        result = cursor.execute(
            """
            UPDATE products
            SET stock = stock + ?, updated_at = ?
            WHERE id = ?
            """,
            (quantity, self._now(), product_id),
        )
        if result.rowcount == 0:
            raise ValueError(f"Product id {product_id} does not exist.")
        self.connection.commit()

    def list_products(self) -> list[Product]:
        cursor = self.connection.cursor()
        rows = cursor.execute(
            "SELECT id, name, price, stock FROM products ORDER BY id"
        ).fetchall()
        return [
            Product(id=row["id"], name=row["name"], price=row["price"], stock=row["stock"])
            for row in rows
        ]

    def process_sale(self, product_id: int, quantity: int) -> float:
        cursor = self.connection.cursor()
        row = cursor.execute(
            "SELECT id, price, stock FROM products WHERE id = ?", (product_id,)
        ).fetchone()
        if row is None:
            raise ValueError(f"Product id {product_id} does not exist.")

        current_stock = row["stock"]
        if quantity > current_stock:
            raise ValueError(
                f"Insufficient stock for product id {product_id}. "
                f"Requested {quantity}, available {current_stock}."
            )

        unit_price = float(row["price"])
        total_amount = unit_price * quantity
        sold_at = self._now()

        try:
            cursor.execute("BEGIN")
            cursor.execute(
                """
                UPDATE products
                SET stock = stock - ?, updated_at = ?
                WHERE id = ?
                """,
                (quantity, sold_at, product_id),
            )
            cursor.execute(
                """
                INSERT INTO sales (product_id, quantity, unit_price, total_amount, sold_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (product_id, quantity, unit_price, total_amount, sold_at),
            )
            self.connection.commit()
        except sqlite3.Error:
            self.connection.rollback()
            raise
        return total_amount

    def list_sales(self) -> list[sqlite3.Row]:
        cursor = self.connection.cursor()
        return cursor.execute(
            """
            SELECT
                s.id,
                p.name AS product_name,
                s.quantity,
                s.unit_price,
                s.total_amount,
                s.sold_at
            FROM sales s
            JOIN products p ON p.id = s.product_id
            ORDER BY s.id
            """
        ).fetchall()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="SQLite-backed POS system")
    parser.add_argument(
        "--db",
        default="pos.db",
        help="Path to sqlite database file (default: pos.db)",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    add_product_parser = subparsers.add_parser("add-product", help="Add a product")
    add_product_parser.add_argument("name")
    add_product_parser.add_argument("price", type=float)
    add_product_parser.add_argument("stock", type=int)

    restock_parser = subparsers.add_parser("restock", help="Increase product stock")
    restock_parser.add_argument("product_id", type=int)
    restock_parser.add_argument("quantity", type=int)

    subparsers.add_parser("list-products", help="List all products")

    sell_parser = subparsers.add_parser("sell", help="Record a sale and reduce stock")
    sell_parser.add_argument("product_id", type=int)
    sell_parser.add_argument("quantity", type=int)

    subparsers.add_parser("list-sales", help="List all recorded sales")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if hasattr(args, "stock") and args.stock < 0:
        raise SystemExit("Stock cannot be negative")
    if hasattr(args, "quantity") and args.quantity <= 0:
        raise SystemExit("Quantity must be greater than zero")
    if hasattr(args, "price") and args.price < 0:
        raise SystemExit("Price cannot be negative")

    db = POSDatabase(db_path=args.db)

    try:
        if args.command == "add-product":
            product_id = db.add_product(args.name, args.price, args.stock)
            print(f"Added product '{args.name}' with id {product_id}")

        elif args.command == "restock":
            db.restock_product(args.product_id, args.quantity)
            print(f"Restocked product id {args.product_id} by {args.quantity}")

        elif args.command == "list-products":
            products = db.list_products()
            if not products:
                print("No products found")
            for product in products:
                print(
                    f"{product.id}: {product.name} | "
                    f"price={product.price:.2f} | stock={product.stock}"
                )

        elif args.command == "sell":
            total = db.process_sale(args.product_id, args.quantity)
            print(
                f"Sale recorded for product id {args.product_id}; "
                f"total amount={total:.2f}"
            )

        elif args.command == "list-sales":
            sales = db.list_sales()
            if not sales:
                print("No sales found")
            for sale in sales:
                print(
                    f"{sale['id']}: {sale['product_name']} x{sale['quantity']} "
                    f"@ {sale['unit_price']:.2f} = {sale['total_amount']:.2f} "
                    f"on {sale['sold_at']}"
                )
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    finally:
        db.close()


if __name__ == "__main__":
    main()
