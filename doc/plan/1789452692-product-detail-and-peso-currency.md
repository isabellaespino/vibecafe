# Plan: Product detail page + peso currency display

Derived from `doc/study/1789452657-product-detail-and-peso-currency.md`.

## Outcome

- `/product/<id>/` shows one product's name and price.
- Every product name on the homepage links to its detail page.
- Every price on the site (homepage list + detail page) renders as
  `₱1,234.50`-style Philippine peso formatting, not `$`.

**Still deferred**: cart, checkout, order history, `description`/
`is_active` fields — unchanged from the prior pass.

## Decisions (from the study)

1. URL is `/product/<int:pk>/` (singular, trailing slash) — matches the
   literal request and this project's existing URL style.
2. Currency formatting uses `₱` + `django.contrib.humanize`'s `intcomma`
   filter (thousands separators). `humanize` ships with Django, so this is
   a settings/template change, not a new dependency.
3. No base template introduced yet — still only two pages, so continuing
   to duplicate the `<html>`/`<head>` boilerplate is fine per the existing
   precedent; revisit when a third page (e.g. cart) arrives.

## Steps

### 1. Currency formatting foundation
- [ ] Add `"django.contrib.humanize"` to `INSTALLED_APPS` in
      `vibecafe/settings.py`.

### 2. Product detail view + URL
- [ ] Add `ProductDetailView(DetailView)` (model = `Product`) to
      `products/views.py`.
- [ ] Add `path("product/<int:pk>/", ProductDetailView.as_view(),
      name="product_detail")` to `products/urls.py`.

### 3. Product detail template
- [ ] Create `products/templates/products/product_detail.html`: `{% load
      humanize %}`, show `{{ product.name }}` and `₱{{
      product.price|intcomma }}`, same plain-HTML style as the list
      template.

### 4. Homepage: link + currency
- [ ] In `products/templates/products/product_list.html`:
  - Add `{% load humanize %}`.
  - Wrap each product's name in `<a href="{% url 'product_detail'
    product.pk %}">`.
  - Replace `${{ product.price }}` with `₱{{ product.price|intcomma }}`.

### 5. Manual verification
- [ ] `python manage.py check`.
- [ ] `runserver`; confirm homepage still lists all products, each name is
      a working link.
- [ ] Click through to a product's detail page; confirm name + price
      render, price shows `₱` with correct formatting.
- [ ] Visit `/product/<nonexistent-id>/`; confirm a 404, not a 500.
- [ ] Confirm homepage list price format matches detail page price format
      (both `₱`, both `intcomma`).
- [ ] `python manage.py test` still exits clean.

### 6. Commit
- [ ] One commit on a branch off `main` (e.g.
      `feat/product-detail-peso-currency`):
      `feat: add product detail page and peso currency display`.
      Merge/rendezvous and doc sync happen as their own subsequent workflow
      steps, per CLAUDE.md.

## Explicitly not doing here

- No cart/add-to-cart affordance on the detail page.
- No `description` or `is_active` fields, no image/media handling.
- No shared base template / site-wide nav — still just two pages.
- No locale-switching or multi-currency support — `₱` is hardcoded, matching
  the single-currency scope established in the study.
