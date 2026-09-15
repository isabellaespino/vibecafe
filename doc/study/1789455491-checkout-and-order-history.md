# Feasibility Study — Checkout and order history

## 1. Request

- A logged-in user can check out from the cart page.
- Checkout empties the cart into a saved order.
- The order records product name, price, and quantity **at the time of
  purchase** — later price changes must not alter past orders.
- An order history page lists the user's past orders, each with its items
  and a total.

This is the last piece deferred from every prior pass in this project; the
design was already worked out in the original feasibility study
(`doc/study/1789410787-digital-cafe-feasibility.md` §4.4–4.5, §5.3–5.5,
§5.8) before cart or peso currency existed. This study re-confirms that
design against the codebase as it now stands (a `cart` app with
`CartItem`, peso/`intcomma` display, `django.contrib.humanize`,
login-gated cart) rather than re-deriving it from scratch.

## 2. Current state

- `cart` app: `CartItem(user, product, quantity)`, `UniqueConstraint(user,
  product)`, `on_delete=CASCADE` on both FKs. Cart page (`/cart/`) computes
  a total via `Sum(F(quantity) * F(product__price))`, with a documented
  SQLite gotcha: that aggregate needs `floatformat:2` before `intcomma` to
  render two decimal places (`doc/wiki/overview.md`, "Currency display").
- `products` app: `Product(name, price)` only — no `description`, no
  `is_active`. Nothing currently references a `Product` from outside
  `cart`/`products`.
- No `Order` or `OrderItem` model. No checkout view, no order history
  view.
- Auth: `/accounts/login/` exists; `@login_required` / `LoginRequiredMixin`
  is the established pattern (used by `cart`).

**Verdict:** feasible, same shape as every prior pass — one new app (or
extend `cart`), two new models, two new views, all behind
`@login_required`. The interesting decisions were already made in the
original study; this study's job is confirming they still apply and noting
what's different now that peso/`intcomma` and `cart` exist.

## 3. Where `Order`/`OrderItem` lives: new `orders` app vs. extending `cart`

**Decision: new `orders` app.** `cart` is transient, single-row-per-product,
always-exactly-one-per-user state. `Order`/`OrderItem` is permanent,
multi-row, append-only history. They're different lifecycles reading from
the same `Product` — mirroring how `cart` is already a separate app from
`products` rather than folded into it. `orders` depends on `cart` (checkout
reads `CartItem` rows) but `cart` doesn't need to know `orders` exists.

## 4. `Order` / `OrderItem` model

Unchanged from the original study (§4.4), restated against the current
`Product` shape:

```python
class Order(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)


class OrderItem(models.Model):
    order = models.ForeignKey(Order, related_name="items", on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    product_name = models.CharField(max_length=200)
    unit_price = models.DecimalField(max_digits=6, decimal_places=2)
    quantity = models.PositiveIntegerField()
```

- **`product_name` + `unit_price` snapshot** (original study §5.3): this is
  the literal ask — "records product name, price, and quantity at the time
  of purchase, so later price changes don't alter past orders." Without
  the snapshot, `OrderItem.product.price` would reflect *today's* price,
  silently rewriting history every time an admin edits a `Product`. Copy
  `product.name` → `product_name` and `product.price` → `unit_price` at
  checkout time; render from these snapshot fields, never from
  `product.price`, on the order history page.
- **`on_delete=PROTECT` on `OrderItem.product`** (original study §5.4):
  once a product has been ordered, deleting it from `/admin/` must fail
  loudly (`IntegrityError`) rather than silently deleting order history
  (`CASCADE`) or orphaning the link (`SET_NULL`). Since the snapshot fields
  already carry the display data, `PROTECT` costs nothing at read time —
  it only blocks a destructive admin action. `Product` has no
  `is_active` flag to offer a soft-delete alternative (deferred, per the
  original study §5), so for now a product that's ever been ordered simply
  can't be deleted at all. Worth naming as a real, if narrow, limitation:
  the only way to "retire" a product once it has order history is to leave
  it in the catalog. Reintroducing `is_active` is the natural fix, but
  it's not part of this request.
- **No stored `Order.total`** (original study §5.5): compute on read via
  `Sum(F("quantity") * F("unit_price"))`, same reasoning as the cart total,
  and reusing the same `floatformat:2|intcomma` fix already established for
  that SQLite aggregate quirk (§2 above).
- **`CartItem` keeps `on_delete=CASCADE`** on `product` — unaffected by
  this change; a cart is still not a historical record (original study
  §5.4).

## 5. Checkout as a transaction

Directly from the original study §4.5, unchanged:

1. Load `request.user`'s `CartItem` rows (`select_related("product")`).
2. If empty, redirect back to `/cart/` with a message — nothing to check
   out.
3. Inside `transaction.atomic()`: create an `Order`; for each `CartItem`,
   create an `OrderItem` copying `product`, `product.name` →
   `product_name`, `product.price` → `unit_price`, `quantity`; then delete
   the user's `CartItem` rows.

Wrapping this in `atomic()` matters for the same reason the original study
gave: if a `Product` were deleted mid-checkout (a genuine, if narrow, race
against an admin action), the whole checkout rolls back instead of leaving
a half-built order with an already-emptied cart. `PROTECT` (§4) actually
makes this scenario impossible for a product already in any past order,
but a product could still be deleted between "user loads the cart page"
and "user clicks checkout" if it had never been ordered before — `atomic()`
is what keeps that failure clean.

## 6. Checkout entry point

`POST /checkout/`, `@login_required`, `@require_POST` — a form on the cart
page (`/cart/`), same pattern as the add-to-cart form on the product detail
page: a plain POST button, CSRF-protected, no confirmation step requested
so none is added. On success, redirect to the order history page (or the
new order's detail — see §8) so the user immediately sees what they just
bought, mirroring how add-to-cart redirects to the cart page.

## 7. Order history page

`GET /orders/`, `@login_required`, lists
`Order.objects.filter(user=request.user).order_by("-created_at")
.prefetch_related("items")`. Per the request, each order shows its items
(name, quantity, unit price — from the snapshot fields) and a total.
`prefetch_related` avoids an N+1 across orders' item sets; per-order total
still needs either a per-order `aggregate()` (N queries, one per order) or
a queryset-level `annotate(total=Sum(F("items__quantity") *
F("items__unit_price")))` on the `Order` queryset itself (one query). The
`annotate` form is the better default here since order history is exactly
the kind of page that can grow to many rows per user over time, and it's
no more code than the alternative.

## 8. Order detail — needed, or does history + items already cover it?

The request says the history page lists "past orders with their items and
totals" — read literally, that's satisfied by one page (§7) showing every
order inline with its line items, no separate per-order detail page or
URL. The original study's URL table (§6) had a separate `/orders/<id>/`
detail view, but that was written when order history was still
speculative and paired with a summary-only list view. Given the explicit
ask here is "listing the user's past orders **with their items and
totals**" (not just a summary list), one combined page is the literal,
minimal reading — no separate detail URL, no `OrderDetailView`, no
ownership-filtering bug surface to worry about (original study §7's
"must filter by `user=request.user`, not just check existence" caveat
doesn't even apply if there's no `pk`-addressable detail URL at all).

**Recommendation:** one `/orders/` page, no `/orders/<id>/`. Flag this as a
deliberate reading of "listing... with their items and totals," open to
revision if a distinct per-order permalink turns out to be wanted later.

## 9. Race conditions

Checkout only reads and deletes the user's own `CartItem` rows inside
`atomic()` — no new increment-style race like the cart's add-to-cart
(original study §5.8) exists here, since nothing else concurrently writes
to the same `CartItem` rows being checked out other than the same user's
own double-submission. A double-submitted checkout (double-click) would,
absent any guard, run the transaction twice — but the second run reads
zero `CartItem` rows (already deleted by the first) and simply produces no
second order, which is the same "empty cart, nothing to check out" path as
§5 step 2. No additional locking needed.

## 10. Explicitly out of scope for this pass

- `/orders/<id>/` as a separate URL (§8).
- Editing or cancelling a placed order.
- Order status workflow (preparing, ready, picked up) — original study
  scope note, still holds.
- Tax/service charge — still assumed `sum(unit_price * quantity)` exactly,
  per the original study §9.3.
- Reintroducing `Product.is_active` to allow retiring a product that has
  order history (§4) — noted as the natural next step if it comes up, not
  built here.

## 11. Feasibility verdict

Fully feasible, no new external dependency, no change to `Product` or
`CartItem`. One new app (`orders`), two new models, one checkout view, one
history view, both behind `@login_required`, reusing the
`floatformat:2|intcomma` currency pattern already established for the cart
total. The two things worth getting exactly right, both carried over
directly from the original study: the `product_name`/`unit_price` snapshot
on `OrderItem` (§4) and wrapping checkout in `transaction.atomic()` (§5) —
both cheap now, expensive to retrofit once real order history exists.
