"""Characterization tests: they pin down what process_order does TODAY,
including its odd corners, so the refactor can be proven behaviour-preserving."""
from datetime import date

from orders.pricing import process_order

WINTER = date(2026, 1, 15)
SUMMER = date(2026, 7, 15)


def order(**overrides):
    base = {"items": [{"sku": "A", "qty": 2, "price": 10.0}], "country": "NG"}
    base.update(overrides)
    return base


def test_simple_order_with_nigerian_tax_and_flat_shipping():
    result = process_order(order(), WINTER)
    assert result == {
        "ok": True,
        "subtotal": 20.0,
        "discount": 0,
        "tax": 1.5,
        "shipping": 10,
        "total": 31.5,
        "receipt": "A x2 @ 10.00\nSubtotal: 20.00\nTax: 1.50\nShipping: 10.00\nTotal: 31.50",
    }


def test_empty_or_missing_items_is_an_error_and_not_a_crash():
    assert process_order({"items": []}, WINTER) == {"ok": False, "errors": ["no items"]}
    assert process_order({}, WINTER) == {"ok": False, "errors": ["no items"]}
    assert process_order({"items": None}, WINTER) == {"ok": False, "errors": ["no items"]}


def test_negative_quantity_or_price_reports_the_sku_and_keeps_going():
    items = [
        {"sku": "BAD1", "qty": -1, "price": 5},
        {"sku": "BAD2", "qty": 1, "price": -5},
        {"qty": -3, "price": 1},  # no sku -> "?"
        {"sku": "OK", "qty": 1, "price": 5},
    ]
    result = process_order({"items": items}, WINTER)
    assert result == {
        "ok": False,
        "errors": ["bad item: BAD1", "bad item: BAD2", "bad item: ?"],
    }


def test_zero_quantity_items_are_silently_ignored_everywhere():
    items = [{"sku": "GONE", "qty": 0, "price": 99}, {"sku": "A", "qty": 1, "price": 10}]
    result = process_order({"items": items, "country": "US"}, WINTER)
    assert result["subtotal"] == 10
    assert "GONE" not in result["receipt"]


def test_only_zero_quantity_items_gives_zero_total_not_an_error():
    result = process_order({"items": [{"sku": "A", "qty": 0, "price": 5}], "country": "US"}, WINTER)
    assert result["ok"] is True
    assert result["subtotal"] == 0
    assert result["shipping"] == 25
    assert result["total"] == 25.0


def test_missing_qty_defaults_to_one_and_missing_price_to_zero():
    result = process_order({"items": [{"sku": "A", "price": 7}, {"sku": "FREE"}], "country": "US"}, WINTER)
    assert result["subtotal"] == 7
    assert "A x1 @ 7.00" in result["receipt"]
    assert "FREE x1 @ 0.00" in result["receipt"]


def test_coupons_are_case_and_whitespace_insensitive():
    result = process_order(order(coupon="  save10 "), WINTER)
    assert result["discount"] == 2.0
    assert "Discount: -2.00" in result["receipt"]


def test_flat5_is_capped_at_the_subtotal():
    items = [{"sku": "A", "qty": 1, "price": 3}]
    result = process_order({"items": items, "coupon": "FLAT5", "country": "US"}, WINTER)
    assert result["discount"] == 3
    assert result["total"] == 25.0  # nothing left to pay but shipping


def test_summer_coupon_only_works_in_june_to_august():
    assert process_order(order(coupon="SUMMER"), SUMMER)["discount"] == 4.0
    assert process_order(order(coupon="SUMMER"), WINTER) == {"ok": False, "errors": ["coupon expired"]}
    assert process_order(order(coupon="SUMMER"), date(2026, 5, 31))["ok"] is False
    assert process_order(order(coupon="SUMMER"), date(2026, 9, 1))["ok"] is False
    assert process_order(order(coupon="SUMMER"), date(2026, 6, 1))["ok"] is True


def test_unknown_coupon_is_an_error_and_blank_or_none_coupon_is_not():
    assert process_order(order(coupon="NOPE"), WINTER) == {"ok": False, "errors": ["unknown coupon"]}
    assert process_order(order(coupon="   "), WINTER)["ok"] is True
    assert process_order(order(coupon=None), WINTER)["ok"] is True


def test_item_errors_come_before_coupon_errors():
    items = [{"sku": "BAD", "qty": -1, "price": 1}]
    result = process_order({"items": items, "coupon": "NOPE"}, WINTER)
    assert result["errors"] == ["bad item: BAD", "unknown coupon"]


def test_empty_order_with_bad_coupon_reports_both_errors_in_order():
    result = process_order({"items": [], "coupon": "NOPE"}, WINTER)
    assert result["errors"] == ["no items", "unknown coupon"]


def test_tax_rates_by_country_and_default_for_unknown_country():
    items = [{"sku": "A", "qty": 1, "price": 200}]  # free shipping, no noise
    assert process_order({"items": items, "country": "NG"}, WINTER)["tax"] == 15.0
    assert process_order({"items": items, "country": "US"}, WINTER)["tax"] == 0.0
    assert process_order({"items": items, "country": "GB"}, WINTER)["tax"] == 40.0
    assert process_order({"items": items, "country": "FR"}, WINTER)["tax"] == 20.0
    assert process_order({"items": items}, WINTER)["tax"] == 15.0  # country defaults to NG


def test_tax_rounding_follows_float_representation_not_school_rounding():
    # 9.0 * 0.075 is 0.675 on paper, but the float is just below it, so round() gives 0.67.
    # A "fix" to Decimal/half-up would change this, so pin it.
    items = [{"sku": "A", "qty": 1, "price": 9.0}]
    assert process_order({"items": items, "country": "NG"}, WINTER)["tax"] == 0.67


def test_shipping_rules():
    cheap = [{"sku": "A", "qty": 1, "price": 50}]
    big = [{"sku": "A", "qty": 1, "price": 100}]
    assert process_order({"items": cheap, "country": "NG"}, WINTER)["shipping"] == 10
    assert process_order({"items": cheap, "country": "US"}, WINTER)["shipping"] == 25
    assert process_order({"items": cheap, "country": "NG", "pickup": True}, WINTER)["shipping"] == 0
    assert process_order({"items": big, "country": "US"}, WINTER)["shipping"] == 0  # exactly 100 is free


def test_free_shipping_threshold_is_checked_after_the_discount():
    items = [{"sku": "A", "qty": 1, "price": 105}]
    result = process_order({"items": items, "coupon": "SAVE10", "country": "US"}, WINTER)
    assert result["shipping"] == 25  # 105 - 10.5 = 94.5 < 100


def test_discounted_receipt_layout():
    items = [{"sku": "A", "qty": 1, "price": 200}]
    result = process_order({"items": items, "coupon": "SAVE10", "country": "GB"}, WINTER)
    assert result["receipt"] == (
        "A x1 @ 200.00\nSubtotal: 200.00\nDiscount: -20.00\nTax: 36.00\nShipping: 0.00\nTotal: 216.00"
    )


def test_summer_coupon_covers_all_of_august():
    assert process_order(order(coupon="SUMMER"), date(2026, 8, 31))["ok"] is True
    assert process_order(order(coupon="SUMMER"), date(2026, 6, 30))["ok"] is True


def test_flat5_cap_boundaries():
    def discount_for(price):
        items = [{"sku": "A", "qty": 1, "price": price}]
        return process_order({"items": items, "coupon": "FLAT5", "country": "US"}, WINTER)["discount"]

    assert discount_for(4.5) == 4.5   # capped just below the coupon value
    assert discount_for(5) == 5       # exactly equal
    assert discount_for(5.5) == 5     # coupon fully applies
