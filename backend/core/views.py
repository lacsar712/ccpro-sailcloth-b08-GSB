from django.db import transaction
from django.db.models import Count, Sum
from django.db.models.functions import Coalesce
from rest_framework import status, viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import ClothRoll, DipRun, Loft
from .serializers import (
    RESIN_ZERO,
    ClothRollSerializer,
    DipRunSerializer,
    LoftSerializer,
    quantize_resin,
)


def roll_resin_annotations():
    """布卷树脂合计/浸渍笔数注解，晾晒架角标与树脂累计专页共用同一来源。"""
    return {
        "resin_total": Coalesce(Sum("dip_runs__resin_pct"), RESIN_ZERO),
        "dip_count": Count("dip_runs"),
    }


class LoftViewSet(viewsets.ModelViewSet):
    queryset = Loft.objects.annotate(roll_count=Count("rolls")).all()
    serializer_class = LoftSerializer


class ClothRollViewSet(viewsets.ModelViewSet):
    serializer_class = ClothRollSerializer

    def get_queryset(self):
        qs = (
            ClothRoll.objects.select_related("loft")
            .annotate(**roll_resin_annotations())
            .order_by("loft_id", "roll_code")
        )
        loft_id = self.request.query_params.get("loftId")
        status_param = self.request.query_params.get("status")
        if loft_id:
            qs = qs.filter(loft_id=loft_id)
        if status_param:
            qs = qs.filter(status=status_param)
        return qs


class DipRunViewSet(viewsets.ModelViewSet):
    serializer_class = DipRunSerializer
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        qs = DipRun.objects.select_related("roll", "roll__loft").all()
        roll_id = self.request.query_params.get("rollId")
        if roll_id:
            qs = qs.filter(roll_id=roll_id)
        return qs

    def create(self, request, *args, **kwargs):
        """登记浸渍。

        可选字段 expectedDipCount（提交人看到的该卷当前浸渍笔数）用于乐观并发：
        两名浸胶工基于同一旧笔数交叉登记同一卷时，只有先到的一笔入库，
        另一笔收到 409，需刷新后基于最新笔数重新登记。
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        expected = request.data.get("expectedDipCount")
        if expected is None:
            self.perform_create(serializer)
        else:
            try:
                expected = int(expected)
            except (TypeError, ValueError):
                return Response(
                    {"expectedDipCount": "expectedDipCount 必须是整数"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            roll = serializer.validated_data["roll"]
            with transaction.atomic():
                locked = ClothRoll.objects.select_for_update().get(pk=roll.pk)
                current = locked.dip_runs.count()
                if current != expected:
                    return Response(
                        {
                            "detail": (
                                f"该卷浸渍已变为 {current} 笔，他人可能已抢先登记；"
                                "请刷新后再登记，避免重复入库"
                            ),
                            "dipCount": current,
                        },
                        status=status.HTTP_409_CONFLICT,
                    )
                self.perform_create(serializer)

        headers = self.get_success_headers(serializer.data)
        return Response(
            serializer.data, status=status.HTTP_201_CREATED, headers=headers
        )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def resin_summary(request):
    """树脂累计专页数据。

    每卷返回历史浸渍的树脂百分比明细与算术合计；合计与晾晒架挂签角标
    使用同一数据库聚合（该卷各次树脂相加），从无浸渍的卷合计为 0。
    可按 ?loftId= 与 ?rollId= 筛选。
    """
    qs = (
        ClothRoll.objects.select_related("loft")
        .annotate(**roll_resin_annotations())
        .order_by("loft_id", "roll_code")
    )
    loft_id = request.query_params.get("loftId")
    roll_id = request.query_params.get("rollId")
    if loft_id:
        qs = qs.filter(loft_id=loft_id)
    if roll_id:
        qs = qs.filter(pk=roll_id)

    rolls = list(qs)
    dips = (
        DipRun.objects.filter(roll__in=rolls)
        .order_by("roll_id", "-started_at", "-id")
        .values("id", "roll_id", "started_at", "resin_pct")
    )
    dips_by_roll = {}
    for d in dips:
        dips_by_roll.setdefault(d["roll_id"], []).append(d)

    results = []
    for roll in rolls:
        entries = dips_by_roll.get(roll.pk, [])
        results.append(
            {
                "rollId": roll.pk,
                "rollCode": roll.roll_code,
                "loftId": roll.loft_id,
                "loftName": roll.loft.name,
                "dipCount": roll.dip_count,
                "resinTotal": str(quantize_resin(roll.resin_total)),
                "dips": [
                    {
                        "id": d["id"],
                        "startedAt": d["started_at"].isoformat(),
                        "resinPct": str(d["resin_pct"]),
                    }
                    for d in entries
                ],
            }
        )
    return Response({"results": results})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def dashboard_stats(request):
    data = {
        "loftCount": Loft.objects.count(),
        "rawRollCount": ClothRoll.objects.filter(status=ClothRoll.STATUS_RAW).count(),
        "dippingRollCount": ClothRoll.objects.filter(
            status=ClothRoll.STATUS_DIPPING
        ).count(),
        "curedRollCount": ClothRoll.objects.filter(status=ClothRoll.STATUS_CURED).count(),
        "dipRunCount": DipRun.objects.count(),
    }
    return Response(data)
