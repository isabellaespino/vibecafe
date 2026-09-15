from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.db.models import DecimalField, F, Sum
from django.shortcuts import redirect
from django.views.decorators.http import require_POST
from django.views.generic import ListView

from cart.models import CartItem

from .models import Order, OrderItem


@login_required
@require_POST
def checkout(request):
    cart_items = CartItem.objects.filter(user=request.user).select_related("product")
    if not cart_items:
        return redirect("cart")

    with transaction.atomic():
        order = Order.objects.create(user=request.user)
        OrderItem.objects.bulk_create(
            OrderItem(
                order=order,
                product=item.product,
                product_name=item.product.name,
                unit_price=item.product.price,
                quantity=item.quantity,
            )
            for item in cart_items
        )
        cart_items.delete()

    return redirect("order_history")


class OrderHistoryView(LoginRequiredMixin, ListView):
    template_name = "orders/order_history.html"
    context_object_name = "orders"

    def get_queryset(self):
        return (
            Order.objects.filter(user=self.request.user)
            .prefetch_related("items")
            .annotate(
                total=Sum(
                    F("items__quantity") * F("items__unit_price"),
                    output_field=DecimalField(max_digits=8, decimal_places=2),
                )
            )
            .order_by("-created_at")
        )
