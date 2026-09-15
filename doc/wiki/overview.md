# Vibecafe — codebase manual

Server-rendered Django app for a single cafe. Customers browse a product
list; an admin manages products and accounts through Django's built-in
admin. No frontend framework, no REST API — plain templates.

Background and design rationale live in `doc/study/` and `doc/plan/`; this
page describes what's actually built, kept in sync with `main`.

## Stack

- Django 5.2 (`requirements.txt`)
- SQLite (`db.sqlite3`, gitignored — each environment has its own)
- Django's built-in `auth` and `admin` apps
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
- `products/` — the one app so far. Owns the `Product` model, its admin
  registration, the homepage view, and its own `urls.py` (included at the
  site root from `vibecafe/urls.py`).

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

No other models exist yet. There is no `CartItem`, `Order`, or `OrderItem`.

## Admin

`Product` is registered in `products/admin.py` with `list_display = ("name",
"price")` — no custom admin views, this is Django's default `ModelAdmin`
CRUD.

Accounts are admin-provisioned only: there is no signup view. An admin
creates customer or staff accounts via `/admin/auth/user/add/` (or
`manage.py createsuperuser` for the first admin account). Handing a new
account's initial password to its owner is a manual, out-of-band step —
Django's admin does not email a set-password link.

## URLs

| path | view | auth | notes |
|---|---|---|---|
| `/` | `products.views.ProductListView` | public | lists every `Product`, ordered by name, as `{{ product.name }}` / `${{ product.price }}`. Renders "No products yet." when empty. |
| `/admin/` | Django admin site | staff (`is_staff=True`) | `Product` CRUD lives here. |

## What's deliberately not here yet

Per `doc/plan/1789451642-mvp-product-homepage.md`, this pass stopped at a
product catalog and homepage. Not built:

- Cart (`CartItem`), checkout, or `Order`/`OrderItem` history
- Customer-facing login/logout pages (only the admin login at
  `/admin/login/` exists, via `django.contrib.admin`)
- Product detail pages
- Automated tests (none exist yet — the app is one read-only list view
  over one model; add tests when there's behavior worth covering)

When any of the above gets built, update this page's URL table and data
model section to match.
