# Digital Cafe — Feasibility Study

## 1. Overview

Digital Cafe is a small web app for a cafe: customers browse a product list,
view a product, build a cart, and check out into an order they can look back
at later. Accounts are provisioned by an admin only — there is no
self-registration. The proposed stack is Django + SQLite + Django's built-in
`auth` and `admin` apps, with server-rendered templates (no SPA/JS framework,
no REST API layer).

**Verdict up front:** this is a very good fit for Django. Every piece of the
requested feature set (auth, admin-managed users, admin-managed products,
cart, checkout, order history) maps almost directly onto a Django app with
`django.contrib.auth` and `django.contrib.admin` doing most of the heavy
lifting. The interesting decisions are in the data model, not the framework
choice.

## 2. Scope

**In scope**
- Plain product list (name, price) and a product detail page
- Cart: add product + quantity, adjust/remove, view cart
- Checkout: cart → saved Order, cart is emptied
- Order history: list past orders, view one order's contents
- Admin-only account creation (via Django admin)
- Admin-only product management (via Django admin)

**Explicitly out of scope** (worth stating, since their absence shapes the
data model below)
- Payment processing — "checkout" just converts cart to order, no gateway
- Inventory/stock tracking
- Order status workflow (preparing, ready, picked up, etc.)
- Self-service registration or password reset via email
- Multi-tenancy (this is one cafe, one catalog)

## 3. Why this stack fits

| Requirement | Django feature that covers it |
|---|---|
| Admin creates accounts, no self-registration | `django.contrib.auth` — never expose a signup view; admin uses `/admin/` or `createsuperuser`/`manage.py shell` to add users |
| Admin adds products | `django.contrib.admin` `ModelAdmin` for `Product` — full CRUD UI with zero custom code |
| Server-rendered pages | Django templates + class-based views (`ListView`, `DetailView`, function views for cart/checkout) |
| Login-gated actions | `@login_required` / `LoginRequiredMixin`, built-in `LoginView`/`LogoutView` |
| SQLite | Django's default `DATABASES` config, zero setup |

Nothing here requires DRF, Celery, or any async layer. The whole app is
CRUD over four or five models plus session-authenticated views.

## 4. Data model

### 4.1 Users

Use Django's built-in `User` model directly (`django.contrib.auth.models.User`)
rather than a custom model, **unless** you anticipate needing extra profile
fields (loyalty points, phone number, etc.) — see the trade-off in §5.1.

- `is_staff=True` on the admin's own account is what gates access to
  `/admin/`. Regular customers get `is_staff=False`, `is_active=True`, and a
  password the admin sets (or a Django-generated one communicated out of
  band). No public view ever creates a `User`.

### 4.2 Product

```
Product
- id
- name            CharField
- price           DecimalField(max_digits=6, decimal_places=2)
- description     TextField (blank=True)   # optional, for the detail page
- is_active       BooleanField(default=True)
```

`is_active` lets the admin retire a product (e.g., seasonal drink) without
deleting it and orphaning historical `OrderItem` rows that reference it. The
product list view filters `is_active=True`; the admin can still see and
un-hide inactive products in `/admin/`.

### 4.3 Cart

This is the first real design decision — see §5.2 for the alternative
considered. Recommended shape: **no standalone `Cart` model**, just
cart-line rows scoped to a user.

```
CartItem
- id
- user       FK(User)
- product    FK(Product)
- quantity   PositiveIntegerField
- added_at   DateTimeField(auto_now_add=True)

unique_together: (user, product)
```

- `unique_together` means "add to cart" is an upsert: if the row exists,
  increment `quantity`; otherwise create it. This also makes "view cart" a
  trivial `CartItem.objects.filter(user=request.user)`.
- No `Cart` header row exists because a cart has no attributes of its own in
  this app (no name, no expiry, no multi-cart-per-user). If that changes
  later (e.g. "save for later" as a second list), introduce a `kind` field
  or a real `Cart` model then — see §5.2.

### 4.4 Order / OrderItem

```
Order
- id
- user         FK(User)
- created_at   DateTimeField(auto_now_add=True)

OrderItem
- id
- order         FK(Order, related_name="items")
- product       FK(Product, on_delete=PROTECT)  # see §5.4
- product_name  CharField          # snapshot, see §5.3
- unit_price    DecimalField       # snapshot, see §5.3
- quantity      PositiveIntegerField
```

Order total is **not** stored as a column; it's computed on read
(`sum(unit_price * quantity)`) or annotated with `Sum(F('unit_price') *
F('quantity'))`. See §5.5 for why this is stored-vs-computed, not an
obvious call.

### 4.5 Checkout as a transaction

Checkout is one `django.db.transaction.atomic()` block:

1. Load the user's `CartItem` rows. If empty, redirect back with a message.
2. Create an `Order`.
3. For each `CartItem`, create an `OrderItem` copying `product`, current
   `product.price` (into `unit_price`), `product.name` (into
   `product_name`), and `quantity`.
4. Delete the user's `CartItem` rows.

Wrapping this in `atomic()` matters: if step 3 fails partway (e.g. a product
was deleted between page load and submit), the whole checkout rolls back
instead of leaving a half-built order and an already-emptied cart.

## 5. Where the trade-offs actually are

### 5.1 Built-in `User` vs. custom user model

Django's own documentation recommends starting **every** project with a
custom user model (even an empty subclass of `AbstractUser`), because
swapping `AUTH_USER_MODEL` after the first migration is genuinely painful —
it touches every FK that points at `User`, including ones inside
`django.contrib.admin`'s own tables.

For this app specifically, the stated requirements (name, price, cart,
order history, admin-created accounts) need **no** extra fields on `User` —
no phone number, no loyalty tier, no delivery address. That argues for
using the built-in model as-is and accepting the migration risk, since the
probability of needing custom fields is low and the app is small enough
that a future switch (new project, data migration script) is not
catastrophic.

**Recommendation:** use the built-in `User`, but flag this explicitly to
whoever owns the project — if there's *any* chance of wanting profile
fields (favorite order, birthday for a promo, etc.) within the next year,
paying the one-time cost of a trivial custom user model now is cheaper than
migrating later.

### 5.2 Cart as bare `CartItem` rows vs. a `Cart` header model

Two shapes were considered:

- **Chosen:** `CartItem(user, product, quantity)`, no `Cart` model.
- **Alternative:** `Cart(user, created_at)` + `CartItem(cart FK, product,
  quantity)`, mirroring `Order`/`OrderItem` structurally.

The alternative is more symmetric with `Order`/`OrderItem` and would make a
future "convert cart to order" refactor read almost like a rename. But it
adds a table and a join for zero behavioral gain today, since a cart in
this app is *always* exactly "the current user's pending items" — there's
never more than one per user, it's never listed, and it has no attributes
of its own. Introducing `Cart` now is speculative generality for a
requirement that doesn't exist yet.

The cost of being wrong here is low and localized: if a second kind of
"saved list" is ever needed, it's a small migration (add a `Cart` model,
backfill one row per user, add `cart FK` to `CartItem`), not a rewrite.

### 5.3 Snapshotting price/name on `OrderItem` vs. relying on the `Product` FK

This is the trade-off most likely to bite if skipped. Without
`unit_price`/`product_name` snapshots, an order's displayed total would
silently change every time the admin edits `Product.price` — a customer's
order history would show *today's* prices for a coffee they bought weeks
ago. That's a real correctness bug, not a style preference: order history
is supposed to be a historical record.

The cost of snapshotting is denormalization — `product_name` and
`unit_price` are duplicated data that can drift from the live `Product` row
by design (that's the point). This is the standard e-commerce pattern
(store what was charged, not a pointer to what's charged now) and is worth
the minor redundancy.

### 5.4 `on_delete` behavior for `OrderItem.product`

`Product` can be deactivated (`is_active=False`) but the schema still
allows hard deletion from `/admin/`. If a `Product` is ever deleted while
`OrderItem` rows reference it:

- `CASCADE` would silently delete historical order line items — unacceptable,
  it destroys the customer's order history.
- `SET_NULL` loses the link but keeps the row — survivable *because* of the
  §5.3 snapshot (name/price still render), but loses the ability to click
  through to the product.
- `PROTECT` (recommended) blocks deletion of any product that's ever been
  ordered, forcing the admin to use `is_active=False` instead.

`PROTECT` combined with the `is_active` soft-delete flag is the safer
default: it makes "retire a product" the only supported path once it has
order history, and surfaces the conflict loudly (an `IntegrityError` in
`/admin/`) rather than quietly corrupting order records.

`CartItem.product` can reasonably use `CASCADE`, since a cart is not a
historical record — if a product is deleted, silently dropping it from
active carts is fine.

### 5.5 Computed order total vs. a stored `Order.total` column

Computing the total on read (`Sum(unit_price * quantity)` over `OrderItem`)
avoids a denormalized field that could drift from its line items if a bug
ever mutates `OrderItem` after creation. For an app this size, the read
cost is negligible — order history is a low-traffic, per-user query, and
Django's `annotate()` pushes the sum into SQL.

A stored `Order.total` would save a join on every order-history render at
the cost of a write-time invariant to maintain by hand (nothing in Django
enforces "this column equals the sum of related rows"). Given the low read
volume expected here, computed-on-read is the better default; it's also
strictly easier to reason about in review, since there's no possibility of
`total` and `items` disagreeing.

### 5.6 Anonymous browsing vs. login-required browsing

Because users **cannot self-register**, requiring login to view the product
list would mean an anonymous visitor hits a login wall with no way through
it — a dead end. Recommended split:

- Product list and product detail: public, no login required.
- Cart, checkout, order history: `@login_required`, redirecting to the
  built-in `LoginView` with `?next=` back to where they were.

This also means "add to cart" needs a decision for anonymous users: either
hide/disable the add-to-cart control until logged in, or redirect to login
and preserve the intended action via `?next=`. Given accounts are scarce
(admin-provisioned), the expected traffic pattern is "known customers log
in first," so a simple redirect-to-login on the add-to-cart POST is
sufficient — no need to build a session-based anonymous cart that merges on
login (that complexity is a reasonable thing to defer, and only worth
building if self-registration is added later).

### 5.7 SQLite: fine for this scope, with one caveat to name explicitly

SQLite is a good match for a single-cafe app with modest traffic: it's
zero-ops, ships with Django, and the whole schema here is small enough that
its lack of a separate server process is a pure win during development and
for a low-volume deployment.

The caveat worth stating plainly: SQLite serializes writes (one writer at a
time, file-level locking). For a cafe app, the realistic write hotspot is
checkout during a rush — concurrent checkouts will queue briefly rather
than run in parallel. At the traffic this app implies (a single physical
cafe, orders placed roughly one at a time at a counter or a handful of
concurrent mobile orders), this is very unlikely to be noticeable. If the
app were ever extended to multiple locations or high-concurrency online
ordering, migrating `DATABASES` to Postgres is a config change, not a
rewrite, *provided* the models avoid SQLite-only behavior (they do here —
no raw SQL, no SQLite-specific field types).

### 5.8 Race condition on "add to cart"

`unique_together (user, product)` plus a get-or-increment pattern has a
narrow race window if the same user double-submits "add to cart" (double
click, two tabs). Two options:

- Wrap the get-or-create-and-increment in `transaction.atomic()` with
  `select_for_update()` on the existing row, or
- Use `CartItem.objects.filter(...).update(quantity=F('quantity') + n)`
  as an atomic SQL-level increment, falling back to `create()` on no match
  (a `get_or_create` + `F()`-expression update).

Given SQLite's write serialization (§5.7), this race is already narrower
here than it would be on a multi-writer database, but it costs nothing to
close it correctly with an `F()` expression rather than a Python
read-modify-write.

## 6. Application surface (views/URLs)

| URL | View | Auth | Notes |
|---|---|---|---|
| `/products/` | `ProductListView` | public | plain list: name + price, `is_active=True` |
| `/products/<id>/` | `ProductDetailView` | public | detail page, "add to cart" form (POST) |
| `/cart/` | `cart_view` | required | list `CartItem` rows, quantity update/remove forms |
| `/cart/add/<product_id>/` | `add_to_cart` | required | POST only, redirect to `next` or cart |
| `/cart/item/<id>/remove/` | `remove_from_cart` | required | POST only |
| `/checkout/` | `checkout` | required | POST only, wraps §4.5 transaction |
| `/orders/` | `OrderHistoryListView` | required | `Order.objects.filter(user=request.user)` |
| `/orders/<id>/` | `OrderDetailView` | required | must also filter by `user=request.user` — see §7 |

All mutating endpoints (`add`, `remove`, `checkout`) are POST-only forms
with Django's default CSRF protection — no JS/AJAX needed anywhere in this
feature set.

## 7. Authorization notes

Two different privilege boundaries exist and shouldn't be conflated:

- **`is_staff`** gates `/admin/` — this is how "only an admin can create
  accounts / add products" is enforced. It's Django's existing admin
  permission system; no custom code needed.
- **Object ownership** — a logged-in customer must only ever see *their
  own* cart and orders. Every cart/order queryset must filter by
  `request.user`, and `OrderDetailView.get_queryset()` must filter by
  owner too (not just check existence), otherwise a customer could view
  another customer's order by guessing `/orders/<id>/`. This is the one
  place a naive `DetailView` (unfiltered `get_object_or_404(Order, pk=pk)`)
  is a real access-control bug, not just a style nit.

## 8. Admin workflow (as specified: admin-only account + product creation)

- Product CRUD: register `Product` in `admin.py` with a `ModelAdmin`
  listing `name`, `price`, `is_active` — usable immediately, no custom
  views.
- Account creation: the admin uses `/admin/auth/user/add/` to create a
  customer account (username + password), sets `is_staff=False`. No signup
  view, no email verification flow, nothing to build — this requirement is
  satisfied by *not* adding a registration URL, not by adding new code.
- Handing credentials to the customer (initial password) is a manual,
  out-of-band step (told in person, texted, etc.) — worth naming as a
  process gap, since Django's admin doesn't email a set-password link by
  default the way a "invite user" flow would.

## 9. Open questions worth resolving before build

1. Does "view a single product" need a distinct URL/template, or would a
   detail page beyond the plain list ever show more than name/price/description?
   (Assumed yes, per the requirement — kept as its own `Product.description`
   field and detail template.)
2. Should a retired (`is_active=False`) product still be viewable at its
   detail URL if linked from an old order, or 404? (Recommendation: keep it
   viewable — `OrderItem` already snapshots name/price so this doesn't
   affect order history either way, but a direct product-page link from
   elsewhere shouldn't dead-end.)
3. Any tax/service-charge line, or is the order total strictly
   `sum(unit_price * quantity)`? Not specified — assumed no, kept out of
   the model per §2 scope.

## 10. Feasibility verdict

Fully feasible with the requested stack, and the requested stack is a good
fit — this is close to Django's "hello world" use case (auth + admin +
CRUD + server templates). The framework choice introduces no open
questions; every open question above is a product/data-modeling decision,
not a technical blocker. The main things worth getting right up front are
the price/name snapshot on `OrderItem` (§5.3) and `PROTECT` on
`OrderItem.product` (§5.4) — both are cheap to do at the start and
expensive to retrofit once real order history exists.
