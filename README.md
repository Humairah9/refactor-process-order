# Refactoring `process_order` without changing behaviour

`orders/pricing.py` holds one function, `process_order(order, today)`. It started
as a single 75-line function doing five jobs at once: validating and pricing
items, applying coupons, working out tax, working out shipping, and formatting
a receipt. This repo shows it being split up safely.

## How the history is organised

| Commit | What it does |
|---|---|
| 1 | The original function, untouched |
| 2 | 17 characterization tests, all green on the original |
| 3-7 | One extraction per commit, tests green after each |
| 8 | This README |

Run `python -m pytest -q` at any commit after #2 and it passes.

## The tests

They are *characterization* tests: they pin down what the code does today, not
what it ought to do. That includes odd corners that I would not design on purpose:

- Zero-quantity items vanish silently from the subtotal and the receipt.
- A missing `qty` means 1 and a missing `price` means 0.
- Item errors are reported before coupon errors, and `"no items"` comes first.
- `SUMMER` only works in June to August, and an expired coupon is an error, not a zero discount.
- The free-shipping threshold is checked after the discount, and exactly 100 is free.
- Unknown countries get a 10% tax rate but the international shipping fee.
- Tax uses `round()` on floats, so 9.0 at 7.5% gives 0.67, not 0.68. One test pins this so nobody "fixes" it by accident.

## What I split out, and why

| Function | Why it is separate |
|---|---|
| `_price_items` | Per-item validation and summing is one idea, and its two outputs (subtotal and errors) are returned together. |
| `_calculate_discount` | Coupon rules change most often. Isolating them means a new coupon touches one function. It also owns the "discount never exceeds subtotal" cap. |
| `_calculate_tax` | One line of logic, but now named, and its country lookup is no longer tangled with shipping. |
| `_calculate_shipping` | The pickup, threshold and country rules were a nested if/elif chain. As a function with early returns it reads top to bottom. |
| `_format_receipt` | Presentation has no business sitting between the calculations and the return value. |

`process_order` is now an orchestrator of about 25 lines: validate, price,
discount, tax, shipping, total, receipt. The magic numbers (100, 10, 25, 0.1,
the summer months) became named constants in the last refactor commit.

## What I deliberately did not change

- **Error ordering and the early return.** Tax and shipping are still computed before the error check, as in the original. That is wasteful but harmless, and moving it was not in scope.
- **Floats for money.** A real system should use `Decimal`. That would change behaviour (see the tax test), so it belongs in a separate, deliberate change.
- **The return shape.** Callers still get the same dict keys in both the success and error cases.
