from django.views.generic import ListView

from .models import Product


class ProductListView(ListView):
    model = Product
    context_object_name = "products"

    def get_queryset(self):
        return Product.objects.order_by("name")
