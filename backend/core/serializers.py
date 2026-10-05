from decimal import Decimal

from django.db.models import Sum
from rest_framework import serializers

from .models import ClothRoll, DipRun, Loft
from .rules import can_mark_roll_cured


class LoftSerializer(serializers.ModelSerializer):
    rollCount = serializers.SerializerMethodField()

    class Meta:
        model = Loft
        fields = ("id", "name", "location", "notes", "rollCount", "created_at")
        read_only_fields = ("id", "rollCount", "created_at")

    def get_rollCount(self, obj):
        if hasattr(obj, "roll_count"):
            return obj.roll_count
        return obj.rolls.count()


class ClothRollSerializer(serializers.ModelSerializer):
    loftId = serializers.PrimaryKeyRelatedField(source="loft", queryset=Loft.objects.all())
    rollCode = serializers.CharField(source="roll_code")
    fabricWeightGsm = serializers.IntegerField(source="fabric_weight_gsm", required=False)
    loftName = serializers.CharField(source="loft.name", read_only=True)
    resinTotal = serializers.SerializerMethodField()

    class Meta:
        model = ClothRoll
        fields = (
            "id",
            "loftId",
            "loftName",
            "rollCode",
            "status",
            "fabricWeightGsm",
            "notes",
            "resinTotal",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "loftName", "resinTotal", "created_at", "updated_at")

    def get_resinTotal(self, obj):
        # 晾晒架挂签角标口径：库里该卷各次树脂相加；无浸渍为算出的 0。
        total = getattr(obj, "resin_total", None)
        if total is None:
            total = obj.dip_runs.aggregate(t=Sum("resin_pct"))["t"] or Decimal("0.00")
        return total

    def validate(self, attrs):
        loft = attrs.get("loft") or getattr(self.instance, "loft", None)
        roll_code = attrs.get("roll_code") or getattr(self.instance, "roll_code", None)
        if loft and roll_code:
            qs = ClothRoll.objects.filter(loft=loft, roll_code=roll_code)
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError({"rollCode": "同一帆布间卷号必须唯一"})

        new_status = attrs.get("status")
        if new_status == ClothRoll.STATUS_CURED:
            roll = self.instance
            if roll is None:
                raise serializers.ValidationError(
                    {"status": "新建布卷不能直接设为已固化"}
                )
            # 合并未提交字段到临时视角：用当前实例校验
            ok, msg = can_mark_roll_cured(roll)
            if not ok:
                raise serializers.ValidationError({"status": msg})
        return attrs


class DipRunSerializer(serializers.ModelSerializer):
    rollId = serializers.PrimaryKeyRelatedField(
        source="roll", queryset=ClothRoll.objects.all()
    )
    startedAt = serializers.DateTimeField(source="started_at")
    resinPct = serializers.DecimalField(source="resin_pct", max_digits=5, decimal_places=2)
    cureHours = serializers.DecimalField(
        source="cure_hours",
        max_digits=6,
        decimal_places=2,
        required=False,
        allow_null=True,
    )
    rollCode = serializers.CharField(source="roll.roll_code", read_only=True)
    loftName = serializers.CharField(source="roll.loft.name", read_only=True)

    class Meta:
        model = DipRun
        fields = (
            "id",
            "rollId",
            "rollCode",
            "loftName",
            "startedAt",
            "resinPct",
            "cureHours",
            "notes",
            "created_at",
        )
        read_only_fields = ("id", "rollCode", "loftName", "created_at")
        # 关掉自动唯一性校验：重复/并发登记统一交给数据库唯一约束
        # uniq_dip_roll_started，由 DipRunViewSet.create 幂等返回已入库记录。
        validators = []


class ResinEntrySerializer(serializers.Serializer):
    """树脂累计专页的单笔浸渍明细。"""

    id = serializers.IntegerField()
    startedAt = serializers.DateTimeField(source="started_at")
    resinPct = serializers.DecimalField(
        source="resin_pct", max_digits=5, decimal_places=2
    )
    cureHours = serializers.DecimalField(
        source="cure_hours", max_digits=6, decimal_places=2, allow_null=True
    )
    notes = serializers.CharField()


class ResinRollSerializer(serializers.Serializer):
    """一卷的树脂累计：历史百分比明细 + 算术合计（与挂签角标同口径）。"""

    rollId = serializers.IntegerField(source="id")
    rollCode = serializers.CharField(source="roll_code")
    loftId = serializers.IntegerField(source="loft_id")
    loftName = serializers.CharField(source="loft.name")
    entries = ResinEntrySerializer(source="dip_runs", many=True)
    total = serializers.DecimalField(
        source="resin_total", max_digits=12, decimal_places=2
    )
