"""Tiny synthetic fixtures test software behavior; they are NEVER analytical evidence."""
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import zipfile

import numpy as np

from olist_analytics.config import FILES, ROOT
from olist_analytics import intake
from olist_analytics.statistics import wilson_interval


class OrderGrainTests(unittest.TestCase):
    def setUp(self):
        self.con = sqlite3.connect(":memory:")
        self.con.executescript((ROOT / "sql/01_schema.sql").read_text())
        self.con.execute("INSERT INTO customers VALUES ('c1','u1','00123','City','SP')")
        self.con.execute("INSERT INTO products(product_id) VALUES ('p1')")
        self.con.execute("INSERT INTO sellers(seller_id) VALUES ('s1')")
        self.con.execute("INSERT INTO orders VALUES ('o1','c1','delivered','2018-01-01 08:00:00',NULL,NULL,'2018-01-05 23:59:59','2018-01-05 00:00:00')")
        self.con.execute("INSERT INTO orders VALUES ('o2','c1','delivered','2018-01-01 08:00:00',NULL,NULL,NULL,'2018-01-05 00:00:00')")
        self.con.executemany("INSERT INTO order_items VALUES ('o1',?,'p1','s1',NULL,?,?)", [(1,10,2),(2,20,3)])
        self.con.executemany("INSERT INTO order_payments VALUES ('o1',?,'credit_card',1,?)", [(1,15),(2,20)])
        self.con.executemany("INSERT INTO order_reviews VALUES (?,'o1',?,NULL,NULL,?,?)", [
            ('r1',1,'2018-01-04 00:00:00','2018-01-04 09:00:00'),
            ('r2',5,'2018-01-06 00:00:00','2018-01-06 09:00:00')])
        self.con.executescript((ROOT / "sql/02_order_fact.sql").read_text())

    def tearDown(self):
        self.con.close()

    def test_many_to_many_joins_preserve_totals(self):
        row = self.con.execute("SELECT item_count,payment_record_count,merchandise_value_brl,freight_value_brl,payment_value_brl,review_score,review_count FROM order_fact WHERE order_id='o1'").fetchone()
        self.assertEqual(row, (2,2,30,5,35,5,2))
        self.assertEqual(self.con.execute("SELECT COUNT(*) FROM order_fact").fetchone()[0], 2)

    def test_estimated_date_is_inclusive(self):
        self.assertEqual(self.con.execute("SELECT is_late FROM order_fact WHERE order_id='o1'").fetchone()[0], 0)
        self.con.execute("UPDATE orders SET order_delivered_customer_date='2018-01-06 00:00:00' WHERE order_id='o1'")
        self.assertEqual(self.con.execute("SELECT is_late FROM order_fact WHERE order_id='o1'").fetchone()[0], 1)

    def test_missing_actual_is_not_on_time(self):
        self.assertEqual(self.con.execute("SELECT delivery_eligible,is_late,delivery_days FROM order_fact WHERE order_id='o2'").fetchone(), (0,None,None))

    def test_impossible_date_and_canceled_status_are_excluded(self):
        for actual,status in [("2017-12-31 00:00:00","delivered"),("2018-01-05 00:00:00","canceled")]:
            self.con.execute("UPDATE orders SET order_delivered_customer_date=?,order_status=? WHERE order_id='o1'", (actual,status))
            self.assertEqual(self.con.execute("SELECT delivery_eligible,is_late FROM order_fact WHERE order_id='o1'").fetchone(), (0,None))

    def test_foreign_key_rejects_orphan(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.con.execute("INSERT INTO order_payments VALUES ('missing-order',1,'voucher',1,10)")


class SourceProtectionTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.base = Path(self.directory.name)
        self.patches = [patch.object(intake, key, self.base / folder) for key,folder in [("RAW","raw"),("EXTERNAL","external"),("REPORTS","reports")]]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.directory.cleanup()

    def archive(self, extra=False):
        path = self.base / "fixture.zip"
        with zipfile.ZipFile(path,"w") as z:
            for name in FILES.values():
                z.writestr(name, "test-only-header\n")
            if extra:
                z.writestr("../escape.csv", "unsafe")
        return path

    def test_archive_rejects_unexpected_path(self):
        with self.assertRaises(ValueError):
            intake.acquire(self.archive(extra=True))
        self.assertFalse(any(intake.RAW.iterdir()))

    def test_repeated_acquire_is_idempotent_and_tampering_fails(self):
        archive = self.archive()
        manifest = intake.acquire(archive)
        self.assertEqual(intake.acquire(archive), manifest)
        self.assertEqual(intake.verify_raw(), manifest["raw_sha256"])
        changed = intake.RAW / FILES["orders"]
        changed.write_text("modified-original")
        with self.assertRaises(ValueError):
            intake.verify_raw()
        with self.assertRaises(ValueError):
            intake.acquire(archive)
        self.assertEqual(changed.read_text(), "modified-original")


class StatisticalBoundaryTests(unittest.TestCase):
    def test_wilson_boundary_samples_and_no_observations(self):
        low,high = wilson_interval([0,10,0], [10,10,0])
        self.assertAlmostEqual(low[0],0)
        self.assertAlmostEqual(high[0],0.2775327998628892)
        self.assertAlmostEqual(low[1],1-high[0])
        self.assertAlmostEqual(high[1],1)
        self.assertTrue(np.isnan(low[2]) and np.isnan(high[2]))

    def test_wilson_rejects_invalid_counts(self):
        with self.assertRaises(ValueError):
            wilson_interval(11,10)


if __name__ == "__main__":
    unittest.main()
