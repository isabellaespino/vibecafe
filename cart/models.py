from django.conf import settings
from django.db import models

from products.models import Product


class CartItem(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "product"], name="unique_cart_item_per_user_product")
        ]

    def __str__(self):
        return f"{self.quantity} x {self.product.name}"

    @property
    def subtotal(self):
        return self.quantity * self.product.price
