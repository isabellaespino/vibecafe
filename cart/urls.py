from django.urls import path

from .views import CartView, add_to_cart

urlpatterns = [
    path("cart/", CartView.as_view(), name="cart"),
    path("cart/add/<int:product_id>/", add_to_cart, name="add_to_cart"),
]
