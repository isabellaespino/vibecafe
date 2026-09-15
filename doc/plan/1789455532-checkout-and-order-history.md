# Plan: Checkout and order history

Derived from `doc/study/1789455491-checkout-and-order-history.md`.

## Outcome

- A logged-in user on `/cart/` can submit a checkout form that atomically
  turns their `CartItem` rows into an `Order` + `OrderItem` rows (snapshot
  of product name/price/quantity) and empties the cart.
- `/orders/` lists the logged-in user's past orders, newest first, each
  showing its line items (name, quantity, unit price at time of purchase)
  and an order total, all in peso formatting.
- Later edits to `Product.price` never change what a past order displays.

**Deferred**: `/orders/<id>/` as a separate URL, editing/cancelling
orders, order status workflow, tax/service charge, reintroducing
`Product.is_active`.

## Decisions (from the study)

1. New `orders` app: `Order`, `OrderItem`, checkout view, order history
   view. Separate from `cart` (different lifecycle: transient vs.
   permanent/append-only).
2. `OrderItem` snapshots `product_name` (`CharField`) and `unit_price`
   (`DecimalField`, same precision as `Product.price`) at checkout time;
   the order history page renders from these fields, never from
   `product.price`.
3. `OrderItem.product` uses `on_delete=PROTECT` (not `CASCADE`/`SET_NULL`)
   — a product that's ever been ordered can't be deleted from
   `/admin/`. `CartItem.product` is untouched, stays `CASCADE`.
4. Checkout is one `transaction.atomic()` block: create `Order`, copy each
   `CartItem` into an `OrderItem`, delete the `CartItem` rows. Empty cart
   → redirect to `/cart/`, no-op.
5. No stored `Order.total` — computed via `annotate(total=Sum(F("items__quantity")
   * F("items__unit_price")))` on the `Order` queryset (one query for all
   orders, not one per order). Reuses the `floatformat:2|intcomma` fix
   already established for the cart total's identical SQLite aggregate
   quirk.
6. One combined `/orders/` page (list + each order's items + each order's
   total inline). No separate `/orders/<id>/` detail URL — the literal
   request is "listing... past orders with their items and totals," fully
   covered by one page.
7. Checkout form lives on `/cart/` (a plain POST button, CSRF-protected,
   same style as the existing add-to-cart form), not a separate
   confirmation page — not requested.

## Steps

### 1. `orders` app
- [ ] `python manage.py startapp orders` (do this *before* adding
      `"orders"` to `INSTALLED_APPS` — `cart`'s setup hit
      `ModuleNotFoundError` doing it in the other order).
- [ ] Add `"orders"` to `INSTALLED_APPS`.
- [ ] Define `Order` and `OrderItem` in `orders/models.py` per study §4.
- [ ] `makemigrations orders && migrate` (additive — do not touch
      `db.sqlite3` any other way, per `CLAUDE.md`).

### 2. Checkout view
- [ ] `checkout` view in `orders/views.py`: `@login_required`,
      `@require_POST`. Load the user's `CartItem` rows
      (`select_related("product")`); if none, redirect to `/cart/`
      (optionally with a `messages` note — cart already has a messages
      block pattern to follow). Otherwise, inside `transaction.atomic()`:
      create `Order(user=request.user)`, bulk-create `OrderItem` rows
      copying `product`, `product.name`, `product.price`, `quantity` from
      each `CartItem`, then delete the user's `CartItem` rows. Redirect to
      `/orders/` on success.
- [ ] `path("checkout/", checkout, name="checkout")` in
      `orders/urls.py`; include `orders.urls` from `vibecafe/urls.py`.

### 3. Cart page: checkout form
- [ ] In `cart/templates/cart/cart.html`, add a POST form to `{% url
      'checkout' %}` (CSRF token, submit button), visible only when the
      cart has items (reuse the existing `{% if items %}` block that
      already guards the total).

### 4. Order history view + template
- [ ] `OrderHistoryView` (or function view) in `orders/views.py`:
      `@login_required`; query per study §7 (`annotate` for per-order
      total, `prefetch_related("items")` for line items, ordered
      `-created_at`).
- [ ] `orders/templates/orders/order_history.html`: for each order, its
      `created_at`, its items (`product_name`, `quantity`, `unit_price` —
      peso-formatted, `floatformat:2|intcomma` since `unit_price` is a
      direct column read via `items.all()` so it's actually already
      correctly scaled — verify this during manual testing rather than
      assuming), and the order's `total` (from the `annotate`, needs
      `floatformat:2|intcomma` since it's a SQL aggregate). Empty-state
      message when the user has no past orders.
- [ ] `path("orders/", OrderHistoryView.as_view(), name="order_history")`
      in `orders/urls.py`.

### 5. Manual verification
- [ ] `manage.py check`.
- [ ] Using a throwaway test account (never touch real data, per
      `CLAUDE.md`): add 2+ products to cart with different quantities,
      check out, confirm redirect to `/orders/`, confirm the cart is now
      empty (`/cart/` shows the empty state).
- [ ] Confirm the resulting order on `/orders/` shows the right product
      names, quantities, unit prices, and a correct total, all in `₱`
      formatting with 2 decimal places.
- [ ] Change that product's price via `/admin/`, revisit `/orders/` —
      confirm the past order's displayed unit price and total are
      unchanged (this is the core literal requirement — verify it
      explicitly, don't assume the snapshot works).
- [ ] Attempt to delete, via `/admin/`, a product that appears in an
      order — confirm Django blocks it (`PROTECT`), doesn't silently
      succeed.
- [ ] Check out with an empty cart (e.g. POST to `/checkout/` directly
      with no `CartItem` rows) — confirm a clean redirect, no `Order`
      created, no crash.
- [ ] Anonymous POST to `/checkout/` → redirected to login, same pattern
      as cart (`405` if the post-login redirect is followed as GET —
      expected, same documented caveat as add-to-cart).
- [ ] Place two orders, confirm `/orders/` lists both, newest first, each
      with its own correct items/total (not bleeding into each other).
- [ ] `manage.py test` exits clean.
- [ ] Clean up only the rows this session added (test account, its
      orders/order items) — never `rm db.sqlite3`, never bulk
      `.all().delete()`.

### 6. Commit
- [ ] One commit on a branch off `main` (e.g. `feat/checkout-order-history`):
      `feat: add checkout and order history`. Rendezvous and doc sync are
      separate subsequent steps.

## Explicitly not doing here

- No `/orders/<id>/` detail URL.
- No order editing/cancellation, no status workflow.
- No tax/service charge line.
- No `Product.is_active` soft-delete (would unblock deleting ordered
  products without `PROTECT` violations — out of scope, noted in the
  study as the natural follow-up if it's ever needed).
