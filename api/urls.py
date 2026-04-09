from django.urls import path

from api.views import SalesView, SummaryUsdView, SummaryView, TopProductsView, UploadCsvView

urlpatterns = [
    path('sales', SalesView.as_view(), name='sales'),
    path('analytics/summary', SummaryView.as_view(), name='analytics-summary'),
    path('analytics/summary-usd', SummaryUsdView.as_view(), name='analytics-summary-usd'),
    path('analytics/top-products', TopProductsView.as_view(), name='analytics-top-products'),
    path('analytics/upload-csv', UploadCsvView.as_view(), name='analytics-upload-csv'),
]
