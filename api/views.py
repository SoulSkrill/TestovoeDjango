from __future__ import annotations

from decimal import Decimal

import pandas as pd
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers as drf_serializers
from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from api.analytics import build_summary_items, build_top_products, queryset_to_dataframe
from api.currency import CurrencyServiceError, get_usd_rate
from api.models import Sale
from api.serializers import CsvUploadRequestSerializer, SaleSerializer, SalesQuerySerializer, SummaryQuerySerializer, TopProductsQuerySerializer


class SalesView(APIView):
    @extend_schema(
        summary='Add one or many sales',
        request=SaleSerializer(many=True),
        responses={
            201: inline_serializer(
                name='SalesCreatedResponse',
                fields={'added': drf_serializers.IntegerField()},
            )
        },
    )
    def post(self, request):
        payload = request.data
        if isinstance(payload, dict):
            payload = [payload]
        if not isinstance(payload, list):
            return Response({'detail': 'Expected list of sales objects'}, status=status.HTTP_400_BAD_REQUEST)

        serializer = SaleSerializer(data=payload, many=True)
        serializer.is_valid(raise_exception=True)

        objects = [Sale(**item) for item in serializer.validated_data]
        Sale.objects.bulk_create(objects)

        return Response({'added': len(objects)}, status=status.HTTP_201_CREATED)

    @extend_schema(
        summary='List sales with filters',
        parameters=[SalesQuerySerializer],
        responses={
            200: inline_serializer(
                name='SalesListResponse',
                fields={
                    'total': drf_serializers.IntegerField(),
                    'page': drf_serializers.IntegerField(),
                    'page_size': drf_serializers.IntegerField(),
                    'items': SaleSerializer(many=True),
                },
            )
        },
    )
    def get(self, request):
        query_serializer = SalesQuerySerializer(data=request.query_params)
        query_serializer.is_valid(raise_exception=True)
        params = query_serializer.validated_data

        queryset = Sale.objects.all().order_by('id')
        if params.get('marketplace'):
            queryset = queryset.filter(marketplace=params['marketplace'])
        if params.get('status'):
            queryset = queryset.filter(status=params['status'])
        if params.get('date_from'):
            queryset = queryset.filter(sold_at__gte=params['date_from'])
        if params.get('date_to'):
            queryset = queryset.filter(sold_at__lte=params['date_to'])

        total = queryset.count()
        page = params['page']
        page_size = params['page_size']
        offset = (page - 1) * page_size

        serializer = SaleSerializer(queryset[offset : offset + page_size], many=True)
        return Response(
            {
                'total': total,
                'page': page,
                'page_size': page_size,
                'items': serializer.data,
            }
        )


class SummaryView(APIView):
    @extend_schema(
        summary='Summary metrics for date range',
        parameters=[SummaryQuerySerializer],
        responses={
            200: inline_serializer(
                name='SummaryResponse',
                fields={
                    'date_from': drf_serializers.DateField(),
                    'date_to': drf_serializers.DateField(),
                    'marketplace': drf_serializers.CharField(required=False, allow_null=True),
                    'group_by': drf_serializers.CharField(required=False, allow_null=True),
                    'items': drf_serializers.ListField(child=drf_serializers.JSONField()),
                },
            )
        },
    )
    def get(self, request):
        query_serializer = SummaryQuerySerializer(data=request.query_params)
        query_serializer.is_valid(raise_exception=True)
        params = query_serializer.validated_data

        queryset = Sale.objects.filter(sold_at__gte=params['date_from'], sold_at__lte=params['date_to'])
        if params.get('marketplace'):
            queryset = queryset.filter(marketplace=params['marketplace'])

        frame = queryset_to_dataframe(queryset)
        items = build_summary_items(frame, params.get('group_by'))

        return Response(
            {
                'date_from': params['date_from'],
                'date_to': params['date_to'],
                'marketplace': params.get('marketplace'),
                'group_by': params.get('group_by'),
                'items': items,
            }
        )


class SummaryUsdView(APIView):
    @extend_schema(
        summary='Summary metrics converted to USD',
        parameters=[SummaryQuerySerializer],
        responses={
            200: inline_serializer(
                name='SummaryUsdResponse',
                fields={
                    'date_from': drf_serializers.DateField(),
                    'date_to': drf_serializers.DateField(),
                    'marketplace': drf_serializers.CharField(required=False, allow_null=True),
                    'group_by': drf_serializers.CharField(required=False, allow_null=True),
                    'usd_rate': drf_serializers.FloatField(),
                    'items': drf_serializers.ListField(child=drf_serializers.JSONField()),
                },
            )
        },
    )
    def get(self, request):
        query_serializer = SummaryQuerySerializer(data=request.query_params)
        query_serializer.is_valid(raise_exception=True)
        params = query_serializer.validated_data

        queryset = Sale.objects.filter(sold_at__gte=params['date_from'], sold_at__lte=params['date_to'])
        if params.get('marketplace'):
            queryset = queryset.filter(marketplace=params['marketplace'])

        frame = queryset_to_dataframe(queryset)
        items = build_summary_items(frame, params.get('group_by'))

        try:
            usd_rate = get_usd_rate()
        except CurrencyServiceError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        converted_items = []
        for item in items:
            metrics = item['metrics']
            converted_items.append(
                {
                    'group': item['group'],
                    'metrics': {
                        'total_revenue': _round2(metrics['total_revenue'] / usd_rate),
                        'total_cost': _round2(metrics['total_cost'] / usd_rate),
                        'gross_profit': _round2(metrics['gross_profit'] / usd_rate),
                        'margin_percent': metrics['margin_percent'],
                        'total_orders': metrics['total_orders'],
                        'avg_order_value': _round2(metrics['avg_order_value'] / usd_rate),
                        'return_rate': metrics['return_rate'],
                    },
                }
            )

        return Response(
            {
                'date_from': params['date_from'],
                'date_to': params['date_to'],
                'marketplace': params.get('marketplace'),
                'group_by': params.get('group_by'),
                'usd_rate': usd_rate,
                'items': converted_items,
            }
        )


class TopProductsView(APIView):
    @extend_schema(
        summary='Top products for date range',
        parameters=[TopProductsQuerySerializer],
        responses={
            200: inline_serializer(
                name='TopProductsResponse',
                fields={
                    'date_from': drf_serializers.DateField(),
                    'date_to': drf_serializers.DateField(),
                    'sort_by': drf_serializers.CharField(),
                    'limit': drf_serializers.IntegerField(),
                    'items': drf_serializers.ListField(child=drf_serializers.JSONField()),
                },
            )
        },
    )
    def get(self, request):
        query_serializer = TopProductsQuerySerializer(data=request.query_params)
        query_serializer.is_valid(raise_exception=True)
        params = query_serializer.validated_data

        queryset = Sale.objects.filter(sold_at__gte=params['date_from'], sold_at__lte=params['date_to'])
        frame = queryset_to_dataframe(queryset)
        items = build_top_products(frame, params['sort_by'], params['limit'])

        return Response(
            {
                'date_from': params['date_from'],
                'date_to': params['date_to'],
                'sort_by': params['sort_by'],
                'limit': params['limit'],
                'items': items,
            }
        )


class UploadCsvView(APIView):
    parser_classes = [MultiPartParser, FormParser]
    @extend_schema(
        summary='Upload sales from CSV',
        request={'multipart/form-data': CsvUploadRequestSerializer},
        responses={
            200: inline_serializer(
                name='CsvUploadResponse',
                fields={
                    'loaded_count': drf_serializers.IntegerField(),
                    'error_count': drf_serializers.IntegerField(),
                    'errors': drf_serializers.ListField(child=drf_serializers.JSONField()),
                },
            )
        },
    )
    def post(self, request):
        uploaded = request.FILES.get('file')
        if uploaded is None:
            return Response({'detail': 'CSV file is required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            frame = pd.read_csv(uploaded)
        except Exception as exc:
            return Response({'detail': f'Unable to parse CSV: {exc}'}, status=status.HTTP_400_BAD_REQUEST)

        required_columns = {
            'order_id',
            'marketplace',
            'product_name',
            'quantity',
            'price',
            'cost_price',
            'status',
            'sold_at',
        }
        missing = sorted(required_columns - set(frame.columns))
        if missing:
            return Response(
                {'detail': f"Missing required columns: {', '.join(missing)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        valid_objects = []
        errors = []

        for row_number, row in enumerate(frame.to_dict(orient='records'), start=2):
            normalized = {k: (None if pd.isna(v) else v) for k, v in row.items()}
            serializer = SaleSerializer(data=normalized)
            if serializer.is_valid():
                valid_objects.append(Sale(**serializer.validated_data))
            else:
                errors.append({'row': row_number, 'message': _flatten_errors(serializer.errors)})

        if valid_objects:
            Sale.objects.bulk_create(valid_objects)

        return Response(
            {
                'loaded_count': len(valid_objects),
                'error_count': len(errors),
                'errors': errors,
            }
        )


def _flatten_errors(errors_dict) -> str:
    messages = []
    for field, messages_list in errors_dict.items():
        if isinstance(messages_list, list):
            for message in messages_list:
                messages.append(f'{field}: {message}')
        else:
            messages.append(f'{field}: {messages_list}')
    return '; '.join(messages)


def _round2(value: float | Decimal) -> float:
    return round(float(value), 2)


