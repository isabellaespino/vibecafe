from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import DecimalField, F, Sum
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST
from django.views.generic import TemplateView

from products.models import Product

from .forms import AddToCartForm
from .models import CartItem


@login_required
@require_POST
def add_to_cart(request, product_id):
    product = get_object_or_404(Product, pk=product_id)
    form = AddToCartForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Enter a valid quantity.")
        return redirect("product_detail", pk=product.pk)

    quantity = form.cleaned_data["quantity"]
    item, created = CartItem.objects.get_or_create(
        user=request.user, product=product, defaults={"quantity": quantity}
    )
    if not created:
        CartItem.objects.filter(pk=item.pk).update(quantity=F("quantity") + quantity)

    return redirect("cart")


class CartView(LoginRequiredMixin, TemplateView):
    template_name = "cart/cart.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        items = CartItem.objects.filter(user=self.request.user).select_related("product").order_by("product__name")
        total = items.aggregate(
            total=Sum(F("quantity") * F("product__price"), output_field=DecimalField(max_digits=8, decimal_places=2))
        )["total"]
        context["items"] = items
        context["total"] = total or 0
        return context
