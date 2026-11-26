from datetime import date

import pytest

from nico.bills import Bill, Payment, due_date, estimate, installment_of, month_bills


def make_bill(**kw):
    base = {"id": "b1", "name": "Luz", "due_day": 10, "amount_cents": None, "method_id": "m1"}
    return Bill(**{**base, **kw})


def test_due_date_clamps_to_last_day():
    assert due_date(31, 2026, 2) == date(2026, 2, 28)
    assert due_date(31, 2028, 2) == date(2028, 2, 29)
    assert due_date(31, 2026, 4) == date(2026, 4, 30)
    assert due_date(15, 2026, 2) == date(2026, 2, 15)


def test_due_date_rejects_invalid_day():
    with pytest.raises(ValueError):
        due_date(0, 2026, 1)
    with pytest.raises(ValueError):
        due_date(32, 2026, 1)


def test_installment_before_start_first_last_and_after_end():
    assert installment_of(2026, 3, 12, 2026, 2) is None
    assert installment_of(2026, 3, 12, 2026, 3) == 1
    assert installment_of(2026, 3, 12, 2027, 2) == 12
    assert installment_of(2026, 3, 12, 2027, 3) is None


def test_estimate_with_0_1_and_5_payments():
    assert estimate([]) is None
    assert estimate([12345]) == 12345
    assert estimate([100, 200, 300, 400, 500]) == 400  # só os 3 últimos


def test_estimate_rounds_half_up_in_integers():
    assert estimate([100, 101]) == 101  # 100,5 -> 101
    assert estimate([100, 100, 101]) == 100  # 100,33 -> 100


def test_month_bills_fixed_amount_to_pay():
    [item] = month_bills([make_bill(amount_cents=9000)], [], 2026, 2)
    assert item.status == "a_pagar"
    assert item.amount_cents == 9000
    assert not item.estimated
    assert item.installment_number is None


def test_month_bills_due_day_31_in_february():
    [item] = month_bills([make_bill(due_day=31, amount_cents=100)], [], 2026, 2)
    assert item.due_date == date(2026, 2, 28)


def test_month_bills_paid_uses_paid_amount():
    payments = [Payment("b1", 2026, 3, 15000)]
    [item] = month_bills([make_bill(amount_cents=9000)], payments, 2026, 3)
    assert item.status == "paga"
    assert item.amount_cents == 15000
    assert not item.estimated


def test_month_bills_varies_is_estimated_from_last_three():
    payments = [Payment("b1", 2026, m, c) for m, c in [(1, 1000), (2, 2000), (3, 3000), (4, 4000)]]
    [item] = month_bills([make_bill()], payments, 2026, 5)
    assert item.status == "a_pagar"
    assert item.amount_cents == 3000
    assert item.estimated


def test_month_bills_varies_ignores_other_bills_and_future_payments():
    payments = [
        Payment("b2", 2026, 1, 9999),
        Payment("b1", 2026, 6, 7777),
        Payment("b1", 2026, 1, 500),
    ]
    [item] = month_bills([make_bill()], payments, 2026, 3)
    assert item.amount_cents == 500


def test_month_bills_varies_without_history():
    [item] = month_bills([make_bill()], [], 2026, 3)
    assert item.amount_cents is None
    assert item.estimated


def test_month_bills_installments_window():
    bill = make_bill(amount_cents=80000, installments_total=3, start_year=2026, start_month=3)
    assert month_bills([bill], [], 2026, 2) == []
    [first] = month_bills([bill], [], 2026, 3)
    assert (first.installment_number, first.installment_total) == (1, 3)
    [last] = month_bills([bill], [], 2026, 5)
    assert (last.installment_number, last.installment_total) == (3, 3)
    assert month_bills([bill], [], 2026, 6) == []


def test_month_bills_inactive_bill_disappears():
    assert month_bills([make_bill(amount_cents=100, active=False)], [], 2026, 3) == []


def test_month_bills_sorted_by_due_date():
    bills = [
        make_bill(id="b1", name="Água", due_day=20, amount_cents=1),
        make_bill(id="b2", name="Luz", due_day=5, amount_cents=1),
    ]
    assert [b.name for b in month_bills(bills, [], 2026, 3)] == ["Luz", "Água"]


def test_bill_validation():
    with pytest.raises(ValueError):
        make_bill(due_day=32)
    with pytest.raises(ValueError):
        make_bill(installments_total=3)  # falta o início
