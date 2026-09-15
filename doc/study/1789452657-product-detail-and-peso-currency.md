# Feasibility Study — Product detail page + peso currency display

## 1. Request

1. A product detail page at `/product/<id>` showing the product's name and
   price.
2. Each product on the homepage links to its detail page.
3. Currency display changes from dollars to Philippine pesos, everywhere a
   price is shown.

Cart, checkout, and order history stay out of scope, unchanged from the
prior pass (`doc/plan/1789451642-mvp-product-homepage.md`).

## 2. Current state

- `Product` model: `name`, `price` (`DecimalField`, 6 digits / 2 decimals).
  No `description`, no `is_active`.
- One view, `ProductListView`, one URL (`""`), one template
  (`product_list.html`) that renders `$ {{ product.price }}` per item, no
  links.
- No currency handling anywhere beyond a hardcoded `$` in the template.

**Verdict:** both pieces are small, additive changes to the existing
structure — a second `DetailView` + template + URL, and a template-level
formatting change. No model or admin changes needed.

## 3. Product detail page

### 3.1 URL shape

Requested path is `/product/<id>`. Following Django convention (and this
project's existing trailing-slash style on `/admin/` etc.), use
`/product/<int:pk>/`. Singular `product` (not `products`) to match the
literal request — this deliberately diverges from the original feasibility
study's `/products/<id>/` (§6 of the original study), which predates this
request and used the plural to mirror `/products/` as the list root. Since
the list root is now `/` (this project's homepage), there's no naming
collision to avoid, and the literal ask is singular.

### 3.2 View

A plain `DetailView`:

```python
class ProductDetailView(DetailView):
    model = Product
```

`pk_url_kwarg` defaults to `"pk"`, matching `<int:pk>` — no extra config
needed. No queryset filtering required (no `is_active` field exists yet to
filter on; every `Product` row is visible, same as the list).

### 3.3 Template

New `products/templates/products/product_detail.html`, same
no-JS/no-base-template style as the list page (still only two pages total,
so a shared base template is still not worth the abstraction — revisit when
a third page arrives, e.g. cart).

### 3.4 Homepage link

Each `<li>` becomes `<a href="{% url 'product_detail' product.pk %}">`
wrapping the name (price can stay outside or inside the link — recommend
inside, since "click the row" is the expected affordance and there's no
separate action competing for the click, unlike a future cart page with an
add-to-cart button).

## 4. Currency: dollars → Philippine pesos

### 4.1 What actually needs to change

Only one place currently renders a price: the `$` literal in
`product_list.html`. After this change there will be two (list + detail
templates). "Throughout" scopes to both.

### 4.2 Symbol vs. full formatting

Two levels of correctness are available:

- **Minimal:** swap the literal `$` for `₱` (U+20B1 PESO SIGN), keep
  Django's default Decimal rendering (`3.50` → `₱3.50`).
- **Fuller:** also add thousands separators (₱1,234.50) via
  `django.contrib.humanize`'s `intcomma` filter.

`django.contrib.humanize` ships with Django itself — enabling it is a
one-line `INSTALLED_APPS` addition, not a new external dependency, so it
doesn't need separate justification under the CLAUDE.md "no new
dependencies without a study" rule. Given `price` is capped at 6 digits
(max ₱9,999.99) and this is a single cafe's menu, thousands separators are
unlikely to ever matter in practice, but they cost one `INSTALLED_APPS`
line and one filter tag, and prevent an unreadable
`₱10000.00` if the price cap is ever raised. **Recommendation:** do the
fuller version now — cheap, and correct currency formatting is exactly the
kind of thing worth getting right instead of revisiting later per-template.

### 4.3 What this does *not* need

- No `django.conf.locale` / `USE_L10N` locale-switching — the site has one
  audience and one currency; there's no multi-currency requirement in
  scope.
- No new dependency (`babel`, `django-money`, etc.) — a hardcoded `₱`
  prefix plus `intcomma` fully covers "display pesos" for a single-currency
  app. `django-money` would be justified only if the model needed to *know*
  its currency (e.g. multi-currency pricing), which isn't the case: `price`
  is already just a number, and currency is purely a display concern here.
- No change to `Product.price`'s type or the admin — `DecimalField` is
  currency-agnostic; only template rendering changes.

### 4.4 Rendering pattern

```
₱{{ product.price|intcomma }}
```

`intcomma` on a `Decimal` preserves the two decimal places already present
(`DecimalField` renders `3.50`, not `3.5`), so no extra `floatformat`
needed.

## 5. Risk / edge cases

- `intcomma` requires `"django.contrib.humanize"` in `INSTALLED_APPS` — a
  one-line settings change, easy to forget and easy to verify (`{% load
  humanize %}` will raise `TemplateSyntaxError` if missed, so it fails
  loudly, not silently).
- Detail page for a nonexistent `pk` → Django's `DetailView` already
  404s via `get_object_or_404` semantics; no custom handling needed.
- No `is_active` field exists yet, so there's no "retired product" case to
  worry about at the detail URL (§9.2 of the original study doesn't apply
  yet, since that field was deferred).

## 6. Feasibility verdict

Fully feasible, small, additive. Two new files (detail template, and the
view/URL edits are additions to existing files), one settings line for
`humanize`, and a template-only currency change in two places. No schema
migration needed. No new external dependency.
