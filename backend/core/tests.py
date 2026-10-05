from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from .models import ClothRoll, DipRun, Loft

User = get_user_model()


class ResinApiTestCase(TestCase):
    """树脂累计：角标合计、专页合计与库内各次树脂相加三者一致。"""

    def setUp(self):
        self.user = User.objects.create_user(username="worker1", password="pw123456")
        self.client = APIClient()
        self.client.force_authenticate(self.user)

        self.loft_a = Loft.objects.create(name="东帆布间")
        self.loft_b = Loft.objects.create(name="西帆布间")
        self.r1 = ClothRoll.objects.create(loft=self.loft_a, roll_code="A-01")
        self.r2 = ClothRoll.objects.create(loft=self.loft_a, roll_code="A-02")
        self.r3 = ClothRoll.objects.create(loft=self.loft_b, roll_code="B-01")

        now = timezone.now()
        DipRun.objects.create(
            roll=self.r1,
            started_at=now - timedelta(hours=6),
            resin_pct=Decimal("28.50"),
        )
        DipRun.objects.create(
            roll=self.r1,
            started_at=now - timedelta(hours=1),
            resin_pct=Decimal("26.25"),
        )
        DipRun.objects.create(
            roll=self.r3,
            started_at=now - timedelta(hours=2),
            resin_pct=Decimal("30.00"),
        )
        # r2 故意不浸渍：角标/合计必须为 0

    def dips_payload(self, roll, resin_pct, expected=None):
        payload = {
            "rollId": roll.id,
            "startedAt": timezone.now().isoformat(),
            "resinPct": str(resin_pct),
        }
        if expected is not None:
            payload["expectedDipCount"] = expected
        return payload


class ResinSummaryTests(ResinApiTestCase):
    def test_summary_lists_dips_and_arithmetic_total(self):
        res = self.client.get("/api/resin/")
        self.assertEqual(res.status_code, 200)
        rows = {row["rollCode"]: row for row in res.data["results"]}

        r1 = rows["A-01"]
        self.assertEqual(r1["dipCount"], 2)
        self.assertEqual(r1["resinTotal"], "54.75")
        self.assertEqual([d["resinPct"] for d in r1["dips"]], ["26.25", "28.50"])

        r3 = rows["B-01"]
        self.assertEqual(r3["resinTotal"], "30.00")
        self.assertEqual(r3["dipCount"], 1)

    def test_summary_zero_for_roll_without_dips(self):
        res = self.client.get("/api/resin/")
        rows = {row["rollCode"]: row for row in res.data["results"]}
        self.assertEqual(rows["A-02"]["resinTotal"], "0.00")
        self.assertEqual(rows["A-02"]["dipCount"], 0)
        self.assertEqual(rows["A-02"]["dips"], [])

    def test_summary_filter_by_loft_and_roll(self):
        res = self.client.get("/api/resin/", {"loftId": self.loft_a.id})
        self.assertEqual(
            sorted(row["rollCode"] for row in res.data["results"]), ["A-01", "A-02"]
        )

        res = self.client.get("/api/resin/", {"rollId": self.r3.id})
        self.assertEqual(len(res.data["results"]), 1)
        self.assertEqual(res.data["results"][0]["rollCode"], "B-01")
        self.assertEqual(res.data["results"][0]["resinTotal"], "30.00")

    def test_rolls_endpoint_badge_total_matches_summary_and_db(self):
        """晾晒架角标（/api/rolls/ 的 resinTotal）= 专页合计 = 库内各次相加。"""
        rolls_res = self.client.get("/api/rolls/")
        badge = {r["rollCode"]: r for r in rolls_res.data["results"]}
        summary_res = self.client.get("/api/resin/")
        page = {r["rollCode"]: r for r in summary_res.data["results"]}

        for code in ("A-01", "A-02", "B-01"):
            db_total = sum(
                DipRun.objects.filter(roll__roll_code=code).values_list(
                    "resin_pct", flat=True
                ),
                Decimal("0"),
            )
            expected = str(db_total.quantize(Decimal("0.01")))
            self.assertEqual(badge[code]["resinTotal"], expected)
            self.assertEqual(page[code]["resinTotal"], expected)
            self.assertEqual(badge[code]["resinTotal"], page[code]["resinTotal"])

        self.assertEqual(badge["A-02"]["resinTotal"], "0.00")
        self.assertEqual(badge["A-02"]["dipCount"], 0)


class DipConcurrencyTests(ResinApiTestCase):
    def test_create_with_matching_expected_count(self):
        res = self.client.post(
            "/api/dips/", self.dips_payload(self.r1, "10.00", expected=2), format="json"
        )
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual(DipRun.objects.filter(roll=self.r1).count(), 3)

    def test_create_with_stale_expected_count_conflict(self):
        res = self.client.post(
            "/api/dips/", self.dips_payload(self.r1, "10.00", expected=5), format="json"
        )
        self.assertEqual(res.status_code, 409)
        self.assertEqual(DipRun.objects.filter(roll=self.r1).count(), 2)

    def test_two_workers_interleaved_only_one_entry_stored(self):
        """两名浸胶工都基于旧笔数 2 交叉登记同一卷：只许一笔入库。"""
        worker2 = User.objects.create_user(username="worker2", password="pw123456")
        other = APIClient()
        other.force_authenticate(worker2)

        first = self.client.post(
            "/api/dips/", self.dips_payload(self.r1, "10.00", expected=2), format="json"
        )
        second = other.post(
            "/api/dips/", self.dips_payload(self.r1, "20.00", expected=2), format="json"
        )
        self.assertEqual(first.status_code, 201, first.data)
        self.assertEqual(second.status_code, 409, second.data)

        dips = DipRun.objects.filter(roll=self.r1)
        self.assertEqual(dips.count(), 3)

        # 角标与专页合计仍只跟入库的这一笔对齐
        expected_total = str(
            (Decimal("28.50") + Decimal("26.25") + Decimal("10.00")).quantize(
                Decimal("0.01")
            )
        )
        badge = self.client.get(f"/api/rolls/{self.r1.id}/")
        self.assertEqual(badge.data["resinTotal"], expected_total)
        page = self.client.get("/api/resin/", {"rollId": self.r1.id})
        self.assertEqual(page.data["results"][0]["resinTotal"], expected_total)

    def test_create_without_expected_count_still_allowed(self):
        res = self.client.post(
            "/api/dips/", self.dips_payload(self.r2, "12.50"), format="json"
        )
        self.assertEqual(res.status_code, 201, res.data)
        badge = self.client.get(f"/api/rolls/{self.r2.id}/")
        self.assertEqual(badge.data["resinTotal"], "12.50")
        self.assertEqual(badge.data["dipCount"], 1)

    def test_sequential_entries_both_stored_and_totals_grow(self):
        """顺着面板再登一笔：笔数与合计一起加。"""
        res1 = self.client.post(
            "/api/dips/", self.dips_payload(self.r1, "1.00", expected=2), format="json"
        )
        self.assertEqual(res1.status_code, 201, res1.data)
        res2 = self.client.post(
            "/api/dips/", self.dips_payload(self.r1, "2.00", expected=3), format="json"
        )
        self.assertEqual(res2.status_code, 201, res2.data)

        badge = self.client.get(f"/api/rolls/{self.r1.id}/")
        self.assertEqual(badge.data["dipCount"], 4)
        self.assertEqual(badge.data["resinTotal"], "57.75")
        page = self.client.get("/api/resin/", {"rollId": self.r1.id})
        self.assertEqual(page.data["results"][0]["resinTotal"], "57.75")
