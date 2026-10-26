TAX_RATES = {"NG": 0.075, "US": 0.0, "GB": 0.2}


def _price_items(items):
    """Return (subtotal, errors). Zero-quantity items are skipped silently."""
    subtotal = 0
    errors = []
    for item in items:
        qty = item.get("qty", 1)
        price = item.get("price", 0)
        if qty < 0 or price < 0:
            errors.append("bad item: " + str(item.get("sku", "?")))
            continue
        if qty == 0:
            continue
        subtotal += qty * price
    return subtotal, errors


def process_order(order, today):
    """Validate an order, price it, and return a summary dict."""
    errors = []
    items = order.get("items") or []
    if not items:
        errors.append("no items")

    subtotal, item_errors = _price_items(items)
    errors.extend(item_errors)

    discount = 0
    coupon = (order.get("coupon") or "").strip().upper()
    if coupon:
        if coupon == "SAVE10":
            discount = subtotal * 0.10
        elif coupon == "FLAT5":
            discount = 5
        elif coupon == "SUMMER":
            if today.month in (6, 7, 8):
                discount = subtotal * 0.2
            else:
                errors.append("coupon expired")
        else:
            errors.append("unknown coupon")
    if discount > subtotal:
        discount = subtotal
    discounted = subtotal - discount

    country = order.get("country", "NG")
    rate = TAX_RATES.get(country, 0.1)
    tax = round(discounted * rate, 2)

    if order.get("pickup"):
        shipping = 0
    elif discounted >= 100:
        shipping = 0
    elif country == "NG":
        shipping = 10
    else:
        shipping = 25

    total = round(discounted + tax + shipping, 2)

    if errors:
        return {"ok": False, "errors": errors}

    lines = []
    for item in items:
        qty = item.get("qty", 1)
        if qty > 0:
            lines.append("%s x%d @ %.2f" % (item.get("sku", "?"), qty, item.get("price", 0)))
    lines.append("Subtotal: %.2f" % subtotal)
    if discount:
        lines.append("Discount: -%.2f" % discount)
    lines.append("Tax: %.2f" % tax)
    lines.append("Shipping: %.2f" % shipping)
    lines.append("Total: %.2f" % total)

    return {
        "ok": True,
        "subtotal": subtotal,
        "discount": discount,
        "tax": tax,
        "shipping": shipping,
        "total": total,
        "receipt": "\n".join(lines),
    }
