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


def _calculate_discount(coupon_code, subtotal, today):
    """Return (discount, errors). The discount never exceeds the subtotal."""
    discount = 0
    errors = []
    coupon = (coupon_code or "").strip().upper()
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
    return discount, errors


def _calculate_tax(amount, country):
    return round(amount * TAX_RATES.get(country, 0.1), 2)


def _calculate_shipping(amount, country, is_pickup):
    if is_pickup:
        return 0
    if amount >= 100:
        return 0
    if country == "NG":
        return 10
    return 25


def process_order(order, today):
    """Validate an order, price it, and return a summary dict."""
    errors = []
    items = order.get("items") or []
    if not items:
        errors.append("no items")

    subtotal, item_errors = _price_items(items)
    errors.extend(item_errors)

    discount, coupon_errors = _calculate_discount(order.get("coupon"), subtotal, today)
    errors.extend(coupon_errors)
    discounted = subtotal - discount

    country = order.get("country", "NG")
    tax = _calculate_tax(discounted, country)
    shipping = _calculate_shipping(discounted, country, order.get("pickup"))

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
