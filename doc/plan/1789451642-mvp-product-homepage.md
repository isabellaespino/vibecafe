# Plan: MVP — Django scaffold, Product model, admin, homepage listing

Derived from `doc/study/1789410787-digital-cafe-feasibility.md`.

## Outcome

A running Django project where:
- An admin can log into `/admin/` and add/edit/delete `Product` rows
  (name + price) with zero custom admin code.
- A visitor hitting `/` sees every product's name and price, server-rendered,
  no JS.

**Deferred** (per study §2, explicitly out of scope for this pass): cart,
checkout, order history, `CartItem`/`Order`/`OrderItem` models, customer
accounts beyond the admin superuser, product detail pages, `is_active`
soft-delete, `description` field. These come back once cart/checkout is
studied and planned as its own pass — building them now would be scope creep
against "minimal viable."

## Decisions (deviations from / narrowing of the study)

1. **Product model is minimal**: `name` (`CharField`) and `price`
   (`DecimalField(max_digits=6, decimal_places=2)`) only. The study's
   `description` and `is_active` fields (§4.2) exist to support a product
   detail page and order-history integrity — neither exists yet, so adding
   those columns now would be speculative. Add them when the detail page or
   `OrderItem` (§5.3–5.4) actually needs them.
2. **Homepage is the product list**, served at `/` rather than the study's
   `/products/` (§6) — with no cart/detail/checkout pages yet, there's only
   one page, so it *is* the homepage. Revisit the URL scheme when a detail
   page is added.
3. **No custom `User` model.** No accounts feature is in scope yet beyond
   the admin superuser, so the built-in/custom-user trade-off (§5.1) doesn't
   need a decision this pass.
4. **Project package name**: `vibecafe` (matches repo name). **App name**:
   `products` (holds the `Product` model, list view, and admin registration
   — matches Django convention of naming an app after its main model).
5. Django is the CLAUDE.md-mandated stack already, so no new study is needed
   to justify adding it as a dependency; pin it in `requirements.txt` for
   reproducibility.

## Steps

### 1. Project scaffold
- [ ] Create `requirements.txt` pinning Django (latest stable 5.x at time of
      writing).
- [ ] Set up a virtualenv, `pip install -r requirements.txt`.
- [ ] `django-admin startproject vibecafe .` (project files at repo root,
      alongside `doc/`, `CLAUDE.md`).
- [ ] Add a `.gitignore` covering `__pycache__/`, `*.pyc`, `db.sqlite3`,
      `venv/`/`.venv/`, `.env`.
- [ ] Confirm `DATABASES` in `vibecafe/settings.py` is left at the default
      SQLite config (no changes needed).

### 2. `products` app
- [ ] `python manage.py startapp products`.
- [ ] Add `"products"` to `INSTALLED_APPS`.
- [ ] Define `Product` in `products/models.py`:
      ```python
      class Product(models.Model):
          name = models.CharField(max_length=200)
          price = models.DecimalField(max_digits=6, decimal_places=2)

          def __str__(self):
              return self.name
      ```
- [ ] `python manage.py makemigrations products && python manage.py migrate`.

### 3. Admin registration
- [ ] In `products/admin.py`:
      ```python
      from django.contrib import admin
      from .models import Product

      @admin.register(Product)
      class ProductAdmin(admin.ModelAdmin):
          list_display = ("name", "price")
      ```
- [ ] `python manage.py createsuperuser` (manual, local step — not committed
      to the repo; document the command in doc/wiki instead, per study §8).

### 4. Homepage (product list)
- [ ] Add a `product_list` view in `products/views.py` (`ListView` over
      `Product.objects.all()`, ordered by `name`).
- [ ] Add a template `products/templates/products/product_list.html`:
      plain HTML, a heading, and a list/table of `{{ product.name }}` —
      `${{ product.price }}` for each product. No base template needed yet
      (single page); introduce one only when a second page exists.
- [ ] Wire `products/urls.py` with one path (`""` → `product_list`) and
      include it from `vibecafe/urls.py` at the root (`""`), alongside the
      existing `admin/` path.

### 5. Manual verification
- [ ] `python manage.py runserver`.
- [ ] Visit `/admin/`, log in with the superuser, add two or three products
      with distinct names/prices.
- [ ] Visit `/` and confirm all added products render with correct name and
      price, in a plain server-rendered page (view source: no JS framework
      artifacts).
- [ ] Confirm `python manage.py check` and `python manage.py test` (no
      tests yet, but the command should exit clean) both pass.

### 6. Commit
- [ ] One commit: `feat: scaffold Django project with Product model and homepage`
      (per CLAUDE.md: one conventional commit per change). Do this on a
      branch off `main` (e.g. `feat/mvp-product-homepage`), per the
      **execute plan** step of the workflow. Merging back to `main` and
      re-confirming the app runs is the subsequent **rendezvous** step, not
      part of this plan.

## Explicitly not doing here

- No `CartItem`, `Order`, `OrderItem` models or views (study §4.3–4.5).
- No customer-facing accounts/login (study §5.6) — only the admin
  superuser exists.
- No product detail page, no `description`/`is_active` fields.
- No tests beyond the sanity checks in step 5 (add real test coverage when
  there's behavior worth testing — a plain list view over one model doesn't
  justify a test suite yet, but say so explicitly rather than silently
  skipping).
