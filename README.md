# SQLite POS

A lightweight command-line Point of Sale (POS) app with persistent SQLite storage.

## Features

- Products are stored in a SQLite database.
- Each sale automatically reduces stock.
- Every sale is logged in a dedicated sales table.
- Data persists across runs via a local `.db` file.
- Graceful validation for duplicate products and invalid stock/sale operations.

## Usage

```bash
python3 pos.py --db shop.db add-product "Apple" 0.50 100
python3 pos.py --db shop.db restock 1 20
python3 pos.py --db shop.db list-products
python3 pos.py --db shop.db sell 1 3
python3 pos.py --db shop.db list-sales
```

If `--db` is omitted, `pos.db` is used in the current directory.

## Data model

- `products(id, name, price, stock, created_at, updated_at)`
- `sales(id, product_id, quantity, unit_price, total_amount, sold_at)`


## Testing

```bash
python3 -m unittest -v
```
