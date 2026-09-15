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

There is no `Order` or `OrderItem` yet — checkout and order history are
still deferred.

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
| `/accounts/login/` | `django.contrib.auth.views.LoginView` | public | customer-facing login; `?next=` sends the user back where they came from. |
| `/admin/` | Django admin site | staff (`is_staff=True`) | `Product` CRUD lives here. |

## What's deliberately not here yet

Per `doc/plan/1789451642-mvp-product-homepage.md`,
`doc/plan/1789452692-product-detail-and-peso-currency.md`, and
`doc/plan/1789454236-cart.md`, this pass stopped at a product catalog,
homepage, detail page, and cart. Not built:

- Removing or editing a cart item's quantity after it's been added
- Checkout, `Order`/`OrderItem`, order history
- Logout, password reset/change, self-registration
- `description` or `is_active` fields on `Product`
- Any shared base template or site nav (each page is still a standalone
  `<html>` document)
- Automated tests (none exist yet — add tests when there's behavior worth
  covering)

When any of the above gets built, update this page's URL table and data
model section to match.
