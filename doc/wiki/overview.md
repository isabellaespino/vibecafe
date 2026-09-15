# Vibecafe — codebase manual

Server-rendered Django app for a single cafe. Customers browse a product
list; an admin manages products and accounts through Django's built-in
admin. No frontend framework, no REST API — plain templates.

Background and design rationale live in `doc/study/` and `doc/plan/`; this
page describes what's actually built, kept in sync with `main`.

## Stack

- Django 5.2 (`requirements.txt`)
- SQLite (`db.sqlite3`, gitignored — each environment has its own)
- Django's built-in `auth`, `admin`, and `humanize` apps
- Server-rendered templates, no JS framework

## Running it locally

```
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python manage.py migrate
.venv/bin/python manage.py createsuperuser   # to log into /admin/
.venv/bin/python manage.py runserver
```

- Homepage: `http://127.0.0.1:8000/`
- Admin: `http://127.0.0.1:8000/admin/`

## Project layout

- `vibecafe/` — Django project package (settings, root URLconf, WSGI/ASGI).
- `products/` — owns the `Product` model, its admin registration, the list
  and detail views, and its own `urls.py` (included from
  `vibecafe/urls.py`).
- `cart/` — owns `CartItem`, the add-to-cart view, and the cart page view,
  each behind `@login_required`. Its own `urls.py`, included from
  `vibecafe/urls.py`.
- `orders/` — owns `Order`/`OrderItem`, the checkout view, and the order
  history view, each behind `@login_required`. Depends on `cart` (checkout
  reads `CartItem` rows); `cart` doesn't depend on `orders`. Its own
  `urls.py`, included from `vibecafe/urls.py`.
- `templates/registration/login.html` — the customer-facing login page's
  template. Project-level (not inside any app) because login isn't tied to
  any one app's data model; `vibecafe/settings.py` adds `BASE_DIR /
  "templates"` to `TEMPLATES[0]["DIRS"]` so it's found.

## Data model

### `Product` (`products/models.py`)

| field | type |
|---|---|
| `name` | `CharField(max_length=200)` |
| `price` | `DecimalField(max_digits=6, decimal_places=2)` |

Deliberately minimal — no `description`, no `is_active` soft-delete flag.
Those were considered in the feasibility study but deferred until a product
detail page or order history actually needs them (see
`doc/study/1789410787-digital-cafe-feasibility.md` §4.2, §5.3–5.4).

### `CartItem` (`cart/models.py`)

| field | type |
|---|---|
| `user` | `ForeignKey(User, on_delete=CASCADE)` |
| `product` | `ForeignKey(Product, on_delete=CASCADE)` |
| `quantity` | `PositiveIntegerField` |

`UniqueConstraint(user, product)` — one row per user per product; adding a
product already in the cart increments `quantity` instead of creating a
second row. No timestamp field; the cart page orders by `product__name`
instead of insertion order.

`CartItem.subtotal` is a Python property (`quantity * product.price`), not
a stored column — same "compute on read, don't let it drift" reasoning as
the original feasibility study applied to order totals.

### `Order` / `OrderItem` (`orders/models.py`)

| model | field | type |
|---|---|---|
| `Order` | `user` | `ForeignKey(User, on_delete=CASCADE)` |
| `Order` | `created_at` | `DateTimeField(auto_now_add=True)` |
| `OrderItem` | `order` | `ForeignKey(Order, related_name="items", on_delete=CASCADE)` |
| `OrderItem` | `product` | `ForeignKey(Product, on_delete=PROTECT)` |
| `OrderItem` | `product_name` | `CharField(max_length=200)` |
| `OrderItem` | `unit_price` | `DecimalField(max_digits=6, decimal_places=2)` |
| `OrderItem` | `quantity` | `PositiveIntegerField` |

`product_name` and `unit_price` are a **snapshot** taken at checkout time,
copied from `Product.name`/`Product.price`. The order history page always
renders from these fields, never from `product.name`/`product.price` —
that's what makes a later price edit not rewrite past orders. Verified
directly: changing `Product.price` after an order exists leaves the
order's `unit_price` unchanged.

`OrderItem.product` uses `on_delete=PROTECT`, unlike `CartItem.product`'s
`CASCADE` — a product that's ever been ordered can't be deleted from
`/admin/` (raises `ProtectedError`, verified). Since `Product` has no
`is_active` flag, there's currently no way to retire a product once it has
order history; it just has to stay in the catalog. Reintroducing
`is_active` would fix this but hasn't been needed yet.

No stored `Order.total` — computed via `annotate(total=Sum(F("items__quantity")
* F("items__unit_price")))` on the order queryset, same "compute on read"
reasoning as `CartItem.subtotal`, and subject to the same SQLite aggregate
formatting quirk described below (needs `floatformat:2` before
`intcomma`).

## Currency display

Prices are Philippine pesos. There's no currency field on `Product` — `price`
is a plain `DecimalField`; currency is purely a template-rendering concern.
Every template that shows a price does `₱{{ value|intcomma }}` (`intcomma`,
from `django.contrib.humanize`, adds thousands separators, e.g.
`₱1,234.50`). If a new page ever renders a price, follow the same pattern —
don't hardcode `$` or skip `intcomma`.

**Gotcha for computed totals**: a value read straight off a `DecimalField`
column (e.g. `product.price`, or a Python-computed property like
`CartItem.subtotal`) always keeps its 2 decimal places. A value computed by
a SQL aggregate over an expression — e.g. `cart`'s
`Sum(F("quantity") * F("product__price"))` — does not, under SQLite:
Django's SQLite backend only quantizes to `decimal_places` for direct
column reads, not computed expressions, even with `output_field` set
explicitly (`django/db/backends/sqlite3/operations.py`,
`get_decimalfield_converter`). `₱690` instead of `₱690.00` is the visible
symptom. Fix: chain `floatformat:2` before `intcomma` —
`{{ total|floatformat:2|intcomma }}` — on any value that came from a SQL
aggregate, not just `intcomma` alone. See `cart/templates/cart/cart.html`
for the working example.

## Admin

`Product` is registered in `products/admin.py` with `list_display = ("name",
"price")` — no custom admin views, this is Django's default `ModelAdmin`
CRUD.

Accounts are admin-provisioned only: there is no signup view. An admin
creates customer or staff accounts via `/admin/auth/user/add/` (or
`manage.py createsuperuser` for the first admin account). Handing a new
account's initial password to its owner is a manual, out-of-band step —
Django's admin does not email a set-password link.

## Auth (customer-facing)

`/accounts/login/` (`django.contrib.auth.views.LoginView`, wired directly
in `vibecafe/urls.py`, template at `templates/registration/login.html`) is
the only customer-facing auth page. `LOGIN_URL = "login"` in settings, so
`@login_required`/`LoginRequiredMixin` redirect here with `?next=`.

No logout view, no password reset/change, no self-registration —
`/admin/logout/` is the manual escape hatch for testing. Deliberately not
`include("django.contrib.auth.urls")`: that bundle also wires
password-reset/change views, which need their own templates and (for
reset) an email backend — wiring it partially would leave broken,
guessable URLs live.

**Known caveat**: `/cart/add/<id>/` is POST-only and `@login_required`. An
anonymous POST there redirects to login as expected, but after a
successful login the browser follows the redirect with **GET** (browsers
always GET redirect targets), and a GET to a POST-only view returns a
clean `405`. Logging in does not replay the original add-to-cart action —
the user has to go back and submit the form again. This is accepted,
documented behavior (`doc/study/1789454197-cart.md` §5.3), not a bug.

## URLs

| path | view | auth | notes |
|---|---|---|---|
| `/` | `products.views.ProductListView` | public | lists every `Product`, ordered by name; each name links to its detail page. Renders "No products yet." when empty. |
| `/product/<id>/` | `products.views.ProductDetailView` | public | one product's name and price, plus an add-to-cart form (quantity, POST to `/cart/add/<id>/`). 404s on an unknown id. |
| `/cart/` | `cart.views.CartView` | required | lists the logged-in user's `CartItem` rows: product, quantity, peso subtotal, and a cart total. |
| `/cart/add/<product_id>/` | `cart.views.add_to_cart` | required | POST only. Valid quantity → creates or increments the `CartItem`, redirects to `/cart/`. Invalid quantity → redirects back to the product page with an error message (`django.contrib.messages`). |
| `/checkout/` | `orders.views.checkout` | required | POST only. Empty cart → no-op redirect to `/cart/`. Otherwise, atomically creates an `Order` + snapshotted `OrderItem` rows and empties the cart, then redirects to `/orders/`. |
| `/orders/` | `orders.views.OrderHistoryView` | required | lists the logged-in user's past orders, newest first, each with its line items and total. No separate per-order detail URL — this one page covers "orders with their items and totals." |
| `/accounts/login/` | `django.contrib.auth.views.LoginView` | public | customer-facing login; `?next=` sends the user back where they came from. |
| `/admin/` | Django admin site | staff (`is_staff=True`) | `Product` CRUD lives here. |

## What's deliberately not here yet

The full original feature set — catalog, cart, checkout, order history —
is now built (see `doc/plan/` for each pass). Still not built:

- Removing or editing a cart item's quantity after it's been added
- A separate `/orders/<id>/` detail URL (deliberate — see the `orders`
  row in the URL table above)
- Editing or cancelling a placed order, order status workflow, tax/service
  charge line
- Logout, password reset/change, self-registration
- `description` or `is_active` fields on `Product` (the latter would also
  unblock retiring a product that has order history — see the
  `OrderItem.product` note above)
- Any shared base template or site nav (each page is still a standalone
  `<html>` document)
- Automated tests (none exist yet — add tests when there's behavior worth
  covering)

When any of the above gets built, update this page's URL table and data
model section to match.
