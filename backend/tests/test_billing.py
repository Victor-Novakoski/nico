from datetime import date

import pytest

from nico.billing import (
    Card,
    Invoice,
    installment_schedule,
    invoice_for,
    next_invoice,
    person_totals,
    split_by_shares,
    split_installments,
)

# Fechamento dia 10, vencimento dia 17: vence no mesmo mês do fechamento.
SAME_MONTH = Card(closing_day=10, due_day=17)
# Fechamento dia 25, vencimento dia 5: vence no mês seguinte.
NEXT_MONTH = Card(closing_day=25, due_day=5)


@pytest.mark.parametrize(("closing", "due"), [(0, 5), (32, 5), (5, 0), (5, 32), (-1, 5)])
def test_card_rejects_days_out_of_range(closing, due):
    with pytest.raises(ValueError):
        Card(closing_day=closing, due_day=due)


def test_card_accepts_limits():
    Card(closing_day=1, due_day=31)
    Card(closing_day=31, due_day=1)


@pytest.mark.parametrize(
    ("purchase", "closing", "due"),
    [
        (date(2026, 3, 9), date(2026, 3, 10), date(2026, 3, 17)),  # antes
        (date(2026, 3, 10), date(2026, 4, 10), date(2026, 4, 17)),  # no dia: fatura seguinte
        (date(2026, 3, 11), date(2026, 4, 10), date(2026, 4, 17)),  # depois
    ],
)
def test_invoice_for_around_closing_due_after_closing(purchase, closing, due):
    invoice = invoice_for(SAME_MONTH, purchase)
    assert invoice.closing_date == closing
    assert invoice.due_date == due
    assert (invoice.year, invoice.month) == (due.year, due.month)


@pytest.mark.parametrize(
    ("purchase", "closing", "due"),
    [
        (date(2026, 3, 24), date(2026, 3, 25), date(2026, 4, 5)),
        (date(2026, 3, 25), date(2026, 4, 25), date(2026, 5, 5)),
        (date(2026, 3, 26), date(2026, 4, 25), date(2026, 5, 5)),
    ],
)
def test_invoice_for_around_closing_due_before_closing(purchase, closing, due):
    invoice = invoice_for(NEXT_MONTH, purchase)
    assert invoice.closing_date == closing
    assert invoice.due_date == due
    assert (invoice.year, invoice.month) == (due.year, due.month)


def test_due_day_equal_to_closing_day_goes_to_next_month():
    invoice = invoice_for(Card(closing_day=10, due_day=10), date(2026, 3, 1))
    assert invoice.closing_date == date(2026, 3, 10)
    assert invoice.due_date == date(2026, 4, 10)


@pytest.mark.parametrize(
    ("year", "closing"),
    [(2026, date(2026, 2, 28)), (2028, date(2028, 2, 29))],
)
def test_closing_day_31_in_february(year, closing):
    card = Card(closing_day=31, due_day=10)
    invoice = invoice_for(card, date(year, 2, 1))
    assert invoice.closing_date == closing
    assert invoice.due_date == date(year, 3, 10)


def test_closing_day_31_on_last_day_of_february_goes_to_next_invoice():
    invoice = invoice_for(Card(closing_day=31, due_day=10), date(2026, 2, 28))
    assert invoice.closing_date == date(2026, 3, 31)
    assert invoice.due_date == date(2026, 4, 10)


def test_closing_day_31_in_april_is_day_30():
    invoice = invoice_for(Card(closing_day=31, due_day=10), date(2026, 4, 5))
    assert invoice.closing_date == date(2026, 4, 30)
    assert invoice.due_date == date(2026, 5, 10)


def test_due_day_31_in_february():
    invoice = invoice_for(Card(closing_day=5, due_day=31), date(2026, 2, 1))
    assert invoice.closing_date == date(2026, 2, 5)
    assert invoice.due_date == date(2026, 2, 28)


def test_due_day_after_closing_day_stays_in_month_even_when_clamped():
    # Fechamento 30 e vencimento 31 em fevereiro: ambos viram 28, e a fatura continua sendo
    # a de fevereiro. Jogar o vencimento para março repetiria a competência da fatura seguinte.
    card = Card(closing_day=30, due_day=31)
    invoice = invoice_for(card, date(2026, 2, 1))
    assert invoice.closing_date == date(2026, 2, 28)
    assert invoice.due_date == date(2026, 2, 28)
    assert (invoice.year, invoice.month) == (2026, 2)
    assert next_invoice(card, invoice).due_date == date(2026, 3, 31)


@pytest.mark.parametrize("closing_day", range(1, 32))
@pytest.mark.parametrize("due_day", [1, 5, 10, 15, 20, 25, 28, 29, 30, 31])
def test_consecutive_invoices_never_repeat_the_competence(closing_day, due_day):
    card = Card(closing_day=closing_day, due_day=due_day)
    invoice = invoice_for(card, date(2027, 1, 1))  # atravessa fevereiro não bissexto e 2028
    previous = (invoice.year, invoice.month)
    for _ in range(36):
        invoice = next_invoice(card, invoice)
        current = (invoice.year, invoice.month)
        assert current == _next_month(*previous)
        assert invoice.closing_date <= invoice.due_date
        previous = current


def _next_month(year: int, month: int) -> tuple[int, int]:
    return (year + 1, 1) if month == 12 else (year, month + 1)


def test_purchase_in_december_rolls_over_the_year():
    invoice = invoice_for(NEXT_MONTH, date(2026, 12, 30))
    assert invoice.closing_date == date(2027, 1, 25)
    assert invoice.due_date == date(2027, 2, 5)
    assert (invoice.year, invoice.month) == (2027, 2)


def test_next_invoice_walks_forward():
    first = invoice_for(SAME_MONTH, date(2026, 11, 20))
    assert first.closing_date == date(2026, 12, 10)
    second = next_invoice(SAME_MONTH, first)
    assert second.closing_date == date(2027, 1, 10)
    assert second.due_date == date(2027, 1, 17)
    assert next_invoice(SAME_MONTH, first, 2) == next_invoice(SAME_MONTH, second)
    assert next_invoice(SAME_MONTH, first, 0) == first


def test_next_invoice_rejects_negative_steps():
    invoice = invoice_for(SAME_MONTH, date(2026, 3, 1))
    with pytest.raises(ValueError):
        next_invoice(SAME_MONTH, invoice, -1)


def test_invoice_is_frozen():
    invoice = invoice_for(SAME_MONTH, date(2026, 3, 1))
    with pytest.raises(AttributeError):
        invoice.year = 2000  # type: ignore[misc]
    assert isinstance(invoice, Invoice)


def test_split_installments_with_remainder_goes_to_first():
    assert split_installments(10000, 3) == [3334, 3333, 3333]


def test_split_installments_exact():
    assert split_installments(9000, 3) == [3000, 3000, 3000]


def test_split_installments_single():
    assert split_installments(12345, 1) == [12345]


def test_split_installments_zero_total():
    assert split_installments(0, 4) == [0, 0, 0, 0]


@pytest.mark.parametrize(("total", "n"), [(100, 0), (100, -1), (-1, 3)])
def test_split_installments_validation(total, n):
    with pytest.raises(ValueError):
        split_installments(total, n)


def test_split_installments_always_sums_to_total():
    for total in [0, 1, 2, 99, 100, 101, 9999, 10000, 123457]:
        for n in range(1, 25):
            parts = split_installments(total, n)
            assert len(parts) == n
            assert sum(parts) == total
            assert max(parts) - min(parts) <= max(1, total % n)


def test_installment_schedule_12x_crosses_year():
    schedule = installment_schedule(NEXT_MONTH, date(2026, 12, 30), 120000, 12)
    assert len(schedule) == 12
    assert [amount for _, amount in schedule] == [10000] * 12
    first = schedule[0][0]
    assert first.closing_date == date(2027, 1, 25)
    assert first.due_date == date(2027, 2, 5)
    last = schedule[-1][0]
    assert last.closing_date == date(2027, 12, 25)
    assert last.due_date == date(2028, 1, 5)
    due_dates = [invoice.due_date for invoice, _ in schedule]
    assert len(set(due_dates)) == 12
    assert due_dates == sorted(due_dates)


def test_installment_schedule_single_installment():
    schedule = installment_schedule(SAME_MONTH, date(2026, 3, 9), 5000, 1)
    assert schedule == [(invoice_for(SAME_MONTH, date(2026, 3, 9)), 5000)]


def test_installment_schedule_with_remainder():
    schedule = installment_schedule(SAME_MONTH, date(2026, 3, 11), 10000, 3)
    assert [amount for _, amount in schedule] == [3334, 3333, 3333]
    assert [invoice.due_date for invoice, _ in schedule] == [
        date(2026, 4, 17),
        date(2026, 5, 17),
        date(2026, 6, 17),
    ]


def test_installment_schedule_across_short_months():
    card = Card(closing_day=31, due_day=10)
    schedule = installment_schedule(card, date(2026, 1, 15), 3000, 3)
    assert [invoice.closing_date for invoice, _ in schedule] == [
        date(2026, 1, 31),
        date(2026, 2, 28),
        date(2026, 3, 31),
    ]


def test_split_by_shares_even():
    assert split_by_shares(1000, {"ana": 1, "bruno": 1}) == {"ana": 500, "bruno": 500}


def test_split_by_shares_uneven_weights():
    assert split_by_shares(900, {"ana": 2, "bruno": 1}) == {"ana": 600, "bruno": 300}


def test_split_by_shares_leftover_goes_by_sorted_keys():
    # Ordem de inserção diferente da ordem alfabética: a sobra vai para "ana".
    assert split_by_shares(101, {"bruno": 1, "ana": 1}) == {"ana": 51, "bruno": 50}
    assert split_by_shares(100, {"ana": 1, "bruno": 1, "carla": 1}) == {
        "ana": 34,
        "bruno": 33,
        "carla": 33,
    }


def test_split_by_shares_uneven_with_leftover():
    result = split_by_shares(1000, {"ana": 2, "bruno": 1})
    assert result == {"ana": 667, "bruno": 333}


def test_split_by_shares_zero_amount():
    assert split_by_shares(0, {"ana": 1, "bruno": 2}) == {"ana": 0, "bruno": 0}


@pytest.mark.parametrize(
    "shares",
    [{}, {"ana": 0}, {"ana": 1, "bruno": -1}, {"ana": 1.5}],
)
def test_split_by_shares_validation(shares):
    with pytest.raises(ValueError):
        split_by_shares(100, shares)


def test_split_by_shares_always_sums_to_amount():
    weight_sets = [{"ana": 1}, {"ana": 1, "bruno": 1}, {"ana": 2, "bruno": 1}]
    weight_sets.append({"ana": 3, "bruno": 5, "carla": 7})
    for shares in weight_sets:
        for amount in [0, 1, 2, 3, 7, 99, 100, 101, 3333, 10000, 123457]:
            result = split_by_shares(amount, shares)
            assert set(result) == set(shares)
            assert sum(result.values()) == amount
            assert all(v >= 0 for v in result.values())


def test_person_totals_sums_per_person():
    items = [
        (3334, {"ana": 1, "bruno": 1}),
        (1500, {"ana": 1}),
        (900, {"ana": 2, "bruno": 1}),
    ]
    totals = person_totals(items)
    assert totals == {"ana": 1667 + 1500 + 600, "bruno": 1667 + 300}
    assert sum(totals.values()) == 3334 + 1500 + 900


def test_person_totals_empty():
    assert person_totals([]) == {}
