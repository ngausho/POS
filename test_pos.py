import subprocess
import tempfile
import unittest
from pathlib import Path


class PosCliTests(unittest.TestCase):
    def run_cli(self, db_path: Path, *args: str, expect_success: bool = True):
        command = ["python3", "pos.py", "--db", str(db_path), *args]
        result = subprocess.run(command, capture_output=True, text=True)
        if expect_success and result.returncode != 0:
            self.fail(
                f"Command failed: {' '.join(command)}\n"
                f"stdout: {result.stdout}\n"
                f"stderr: {result.stderr}"
            )
        return result

    def test_sale_reduces_stock_and_records_sale(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "shop.db"

            add_result = self.run_cli(db_path, "add-product", "Apple", "1.5", "10")
            self.assertIn("Added product 'Apple'", add_result.stdout)

            sell_result = self.run_cli(db_path, "sell", "1", "3")
            self.assertIn("Sale recorded", sell_result.stdout)
            self.assertIn("4.50", sell_result.stdout)

            products_result = self.run_cli(db_path, "list-products")
            self.assertIn("stock=7", products_result.stdout)

            sales_result = self.run_cli(db_path, "list-sales")
            self.assertIn("Apple x3", sales_result.stdout)
            self.assertIn("= 4.50", sales_result.stdout)

    def test_data_persists_between_commands(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "persist.db"

            self.run_cli(db_path, "add-product", "Milk", "2.5", "5")
            self.run_cli(db_path, "sell", "1", "2")

            # new process call should still see data
            products_result = self.run_cli(db_path, "list-products")
            sales_result = self.run_cli(db_path, "list-sales")

            self.assertIn("Milk", products_result.stdout)
            self.assertIn("stock=3", products_result.stdout)
            self.assertIn("Milk x2", sales_result.stdout)

    def test_restock_increases_stock(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "restock.db"

            self.run_cli(db_path, "add-product", "Bread", "3.0", "2")
            self.run_cli(db_path, "restock", "1", "5")

            products_result = self.run_cli(db_path, "list-products")
            self.assertIn("stock=7", products_result.stdout)

    def test_validation_errors_return_non_zero(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "errors.db"

            self.run_cli(db_path, "add-product", "Eggs", "5", "4")

            duplicate = self.run_cli(
                db_path,
                "add-product",
                "Eggs",
                "5",
                "4",
                expect_success=False,
            )
            self.assertNotEqual(duplicate.returncode, 0)
            self.assertIn("already exists", duplicate.stderr + duplicate.stdout)

            insufficient = self.run_cli(
                db_path,
                "sell",
                "1",
                "100",
                expect_success=False,
            )
            self.assertNotEqual(insufficient.returncode, 0)
            self.assertIn("Insufficient stock", insufficient.stderr + insufficient.stdout)


if __name__ == "__main__":
    unittest.main()
