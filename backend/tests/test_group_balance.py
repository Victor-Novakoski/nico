import pytest

from nico.groups import GroupExpense, Settlement, balances, who_owes_whom


def test_two_members_equal_split() -> None:
    result = balances([GroupExpense("ana", 1000, {"ana": 1, "bia": 1})], [])
    assert result == {"ana": 500, "bia": -500}


def test_three_members_different_weights() -> None:
    result = balances([GroupExpense("ana", 600, {"ana": 1, "bia": 2, "caio": 3})], [])
    assert result == {"ana": 500, "bia": -200, "caio": -300}


def test_partial_settlement() -> None:
    expenses = [GroupExpense("ana", 1000, {"ana": 1, "bia": 1})]
    result = balances(expenses, [Settlement("bia", "ana", 200)])
    assert result == {"ana": 300, "bia": -300}


def test_full_settlement_zeroes_everyone() -> None:
    expenses = [GroupExpense("ana", 1000, {"ana": 1, "bia": 1})]
    result = balances(expenses, [Settlement("bia", "ana", 500)])
    assert result == {"ana": 0, "bia": 0}


def test_leftover_cent_goes_alphabetically() -> None:
    result = balances([GroupExpense("ana", 100, {"ana": 1, "bia": 1, "caio": 1})], [])
    # partes: ana 34, bia 33, caio 33
    assert result == {"ana": 66, "bia": -33, "caio": -33}


def test_payer_outside_shares() -> None:
    result = balances([GroupExpense("caio", 300, {"ana": 1, "bia": 1})], [])
    assert result == {"caio": 300, "ana": -150, "bia": -150}


@pytest.mark.parametrize(
    "expenses, settlements",
    [
        ([], []),
        ([GroupExpense("ana", 100, {"ana": 1, "bia": 1, "caio": 1})], []),
        (
            [
                GroupExpense("ana", 101, {"ana": 2, "bia": 3, "caio": 5}),
                GroupExpense("bia", 7, {"ana": 1, "caio": 1}),
            ],
            [Settlement("caio", "ana", 13)],
        ),
        (
            [GroupExpense("caio", 999, {"ana": 1, "bia": 1})],
            [Settlement("ana", "bia", 1), Settlement("bia", "caio", 50)],
        ),
    ],
)
def test_sum_is_always_zero(expenses: list[GroupExpense], settlements: list[Settlement]) -> None:
    assert sum(balances(expenses, settlements).values()) == 0


@pytest.mark.parametrize("amount", [0, -5])
def test_settlement_must_be_positive(amount: int) -> None:
    with pytest.raises(ValueError):
        balances([], [Settlement("ana", "bia", amount)])


def test_settlement_to_self_is_rejected() -> None:
    with pytest.raises(ValueError):
        balances([], [Settlement("ana", "ana", 100)])


def test_who_owes_whom_simple() -> None:
    assert who_owes_whom({"ana": 500, "bia": -500}) == [("bia", "ana", 500)]


def test_who_owes_whom_zeroes_the_group() -> None:
    expenses = [
        GroupExpense("ana", 101, {"ana": 2, "bia": 3, "caio": 5}),
        GroupExpense("bia", 777, {"ana": 1, "bia": 1, "caio": 1}),
    ]
    start = balances(expenses, [])
    transfers = who_owes_whom(start)
    assert len(transfers) <= len(start) - 1
    settlements = [Settlement(a, b, c) for a, b, c in transfers]
    assert all(v == 0 for v in balances(expenses, settlements).values())


def test_who_owes_whom_empty_when_settled() -> None:
    assert who_owes_whom({}) == []
    assert who_owes_whom({"ana": 0, "bia": 0}) == []


def test_who_owes_whom_is_deterministic_on_ties() -> None:
    result = who_owes_whom({"ana": 100, "bia": 100, "caio": -100, "dani": -100})
    assert result == [("caio", "ana", 100), ("dani", "bia", 100)]


def test_who_owes_whom_rejects_nonzero_sum() -> None:
    with pytest.raises(ValueError):
        who_owes_whom({"ana": 100, "bia": -50})
