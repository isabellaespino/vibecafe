from django.urls import path

from .views import OrderHistoryView, checkout

urlpatterns = [
    path("checkout/", checkout, name="checkout"),
    path("orders/", OrderHistoryView.as_view(), name="order_history"),
]
