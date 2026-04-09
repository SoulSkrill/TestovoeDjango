from __future__ import annotations

from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIClient


class SalesApiTests(TestCase):
    def setUp(self) -> None:
        self.client = APIClient()

    @staticmethod
    def _sale_payload(**overrides):
        payload = {
            'order_id': 'ORD-001',
            'marketplace': 'ozon',
            'product_name': 'USB-C Cable',
            'quantity': 3,
            'price': 450.0,
            'cost_price': 120.0,
            'status': 'delivered',
            'sold_at': '2025-03-15',
        }
        payload.update(overrides)
        return payload

    def test_create_and_filter_sales(self):
        payload = [
            self._sale_payload(order_id='ORD-001', marketplace='ozon'),
            self._sale_payload(order_id='ORD-002', marketplace='ozon', status='returned'),
            self._sale_payload(order_id='ORD-003', marketplace='wildberries'),
        ]
        response = self.client.post('/sales', payload, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data, {'added': 3})

        list_response = self.client.get('/sales', {'marketplace': 'ozon', 'page': 1, 'page_size': 1})
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(list_response.data['total'], 2)
        self.assertEqual(list_response.data['page'], 1)
        self.assertEqual(list_response.data['page_size'], 1)
        self.assertEqual(len(list_response.data['items']), 1)

    def test_future_date_validation(self):
        payload = [self._sale_payload(sold_at='2100-01-01')]
        response = self.client.post('/sales', payload, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('sold_at', str(response.data))


class AnalyticsApiTests(TestCase):
    def setUp(self) -> None:
        self.client = APIClient()
        payload = [
            {
                'order_id': 'ORD-1',
                'marketplace': 'ozon',
                'product_name': 'USB-C Cable',
                'quantity': 2,
                'price': 100.0,
                'cost_price': 60.0,
                'status': 'delivered',
                'sold_at': '2025-03-10',
            },
            {
                'order_id': 'ORD-2',
                'marketplace': 'ozon',
                'product_name': 'USB-C Cable',
                'quantity': 1,
                'price': 100.0,
                'cost_price': 60.0,
                'status': 'returned',
                'sold_at': '2025-03-11',
            },
            {
                'order_id': 'ORD-3',
                'marketplace': 'wildberries',
                'product_name': 'Mouse',
                'quantity': 1,
                'price': 500.0,
                'cost_price': 300.0,
                'status': 'delivered',
                'sold_at': '2025-03-11',
            },
            {
                'order_id': 'ORD-4',
                'marketplace': 'ozon',
                'product_name': 'Keyboard',
                'quantity': 1,
                'price': 700.0,
                'cost_price': 400.0,
                'status': 'cancelled',
                'sold_at': '2025-03-12',
            },
        ]
        response = self.client.post('/sales', payload, format='json')
        self.assertEqual(response.status_code, 201)

    def test_summary_grouped_by_marketplace(self):
        response = self.client.get(
            '/analytics/summary',
            {'date_from': '2025-03-10', 'date_to': '2025-03-12', 'group_by': 'marketplace'},
        )
        self.assertEqual(response.status_code, 200)

        items = {item['group']: item['metrics'] for item in response.data['items']}
        ozon = items['ozon']
        self.assertAlmostEqual(ozon['total_revenue'], 200.0, places=2)
        self.assertAlmostEqual(ozon['total_cost'], 120.0, places=2)
        self.assertAlmostEqual(ozon['gross_profit'], 80.0, places=2)
        self.assertAlmostEqual(ozon['margin_percent'], 40.0, places=2)
        self.assertEqual(ozon['total_orders'], 3)
        self.assertAlmostEqual(ozon['avg_order_value'], 66.67, places=2)
        self.assertAlmostEqual(ozon['return_rate'], 50.0, places=2)

    def test_top_products(self):
        response = self.client.get(
            '/analytics/top-products',
            {
                'date_from': '2025-03-10',
                'date_to': '2025-03-12',
                'sort_by': 'profit',
                'limit': 2,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['items']), 2)
        self.assertEqual(response.data['items'][0]['product_name'], 'Mouse')
        self.assertAlmostEqual(response.data['items'][0]['profit'], 200.0, places=2)

    @patch('api.views.get_usd_rate', return_value=100.0)
    def test_summary_usd(self, _mock_rate):
        response = self.client.get('/analytics/summary-usd', {'date_from': '2025-03-10', 'date_to': '2025-03-12'})
        self.assertEqual(response.status_code, 200)
        self.assertAlmostEqual(response.data['usd_rate'], 100.0, places=2)

        metrics = response.data['items'][0]['metrics']
        self.assertAlmostEqual(metrics['total_revenue'], 7.0, places=2)
        self.assertAlmostEqual(metrics['total_cost'], 4.2, places=2)
        self.assertAlmostEqual(metrics['gross_profit'], 2.8, places=2)
        self.assertAlmostEqual(metrics['avg_order_value'], 1.75, places=2)

    def test_upload_csv(self):
        csv_content = (
            'order_id,marketplace,product_name,quantity,price,cost_price,status,sold_at\n'
            'ORD-10,ozon,Cable,1,100,60,delivered,2025-03-10\n'
            'ORD-11,ozon,Cable,0,100,60,delivered,2025-03-10\n'
            'ORD-12,wildberries,Mouse,2,500,300,returned,2025-03-11\n'
        )
        upload = SimpleUploadedFile('sales.csv', csv_content.encode('utf-8'), content_type='text/csv')
        response = self.client.post('/analytics/upload-csv', {'file': upload})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['loaded_count'], 2)
        self.assertEqual(response.data['error_count'], 1)
        self.assertEqual(response.data['errors'][0]['row'], 3)
