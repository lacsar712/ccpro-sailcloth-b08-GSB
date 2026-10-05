from decimal import Decimal

from django.db import IntegrityError, transaction
from django.db.models import Count, DecimalField, Sum, Value
from django.db.models.functions import Coalesce
from rest_framework import status, viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import ClothRoll, DipRun, Loft
from .serializers import (
    ClothRollSerializer,
    DipRunSerializer,
    LoftSerializer,
    ResinRollSerializer,
)

# 树脂累计唯一口径：库里该卷各次 resin_pct 直接相加；无浸渍时为 0（计算得出，非写死）。
RESIN_TOTAL = Coalesce(
    Sum("dip_runs__resin_pct"),
    Value(Decimal("0.00")),
    output_field=DecimalField(max_digits=12, decimal_places=2),
)


class LoftViewSet(viewsets.ModelViewSet):
    queryset = Loft.objects.annotate(roll_count=Count("rolls")).all()
    serializer_class = LoftSerializer


class ClothRollViewSet(viewsets.ModelViewSet):
    serializer_class = ClothRollSerializer

    def get_queryset(self):
        qs = (
            ClothRoll.objects.select_related("loft")
            .annotate(resin_total=RESIN_TOTAL)
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
        """幂等登记：同一卷同一开始时间只入库一笔。

        两名浸胶工交叉提交同一浸渍事件时，唯一约束 uniq_dip_roll_started
        让后到的一笔直接命中已入库记录并原样返回（200），角标与树脂累计
        专页始终只跟这一笔对齐。
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            with transaction.atomic():
                self.perform_create(serializer)
            instance = serializer.instance
            created = True
        except IntegrityError:
            instance = DipRun.objects.get(
                roll=serializer.validated_data["roll"],
                started_at=serializer.validated_data["started_at"],
            )
            created = False
        out = self.get_serializer(instance)
        headers = self.get_success_headers(out.data)
        return Response(
            out.data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
            headers=headers,
        )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def resin_summary(request):
    """树脂累计专页数据源：每卷历史浸渍百分比明细 + 算术合计。

    合计与晾晒架挂签角标共用 RESIN_TOTAL 口径（库内 Sum），两边永远相等。
    可按帆布间（loftId）与布卷（rollId）筛选。
    """
    qs = (
        ClothRoll.objects.select_related("loft")
        .prefetch_related("dip_runs")
        .annotate(resin_total=RESIN_TOTAL)
        .order_by("loft_id", "roll_code")
    )
    loft_id = request.query_params.get("loftId")
    roll_id = request.query_params.get("rollId")
    if loft_id:
        qs = qs.filter(loft_id=loft_id)
    if roll_id:
        qs = qs.filter(id=roll_id)
    serializer = ResinRollSerializer(qs, many=True)
    return Response({"results": serializer.data})


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
