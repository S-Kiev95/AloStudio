"""The ``ad_id`` filter attribute — which Meta ad a conversation came from.

Compiles the clause only (no DB): the point is that the attribute is
allow-listed, that every operator it advertises builds, and that ad ids
survive the trip as strings.
"""

from __future__ import annotations

import pytest

from app.core.errors import ChatwootHTTPException
from app.core.models_registry import import_all_models
from app.domains.conversations.filter import _ALLOWED_OPERATORS, _build_clause

import_all_models()

pytestmark = pytest.mark.unit

AD = "120210000000000111"


def _clause(operator: str, values: list | None = None):
    return _build_clause(
        {
            "attribute_key": "ad_id",
            "filter_operator": operator,
            "values": values or [],
        }
    )


def test_ad_id_is_allow_listed_with_its_four_operators():
    assert _ALLOWED_OPERATORS["ad_id"] == {
        "equal_to",
        "not_equal_to",
        "is_present",
        "is_not_present",
    }


@pytest.mark.parametrize(
    "operator,values",
    [
        ("equal_to", [AD]),
        ("not_equal_to", [AD]),
        ("is_present", None),
        ("is_not_present", None),
    ],
)
def test_every_advertised_operator_compiles(operator, values):
    sql = str(_clause(operator, values))
    assert "ad_id" in sql


def test_numeric_ad_ids_are_compared_as_strings():
    """A caller may send the id as a JSON number.

    ``ad_id`` is a text column, so an int would compare against varchar and
    quietly match nothing — the values have to be coerced.
    """
    clause = _build_clause(
        {
            "attribute_key": "ad_id",
            "filter_operator": "equal_to",
            "values": [120210000000000111],  # int, not str
        }
    )
    # An expanding IN binds the whole list under a single param, so flatten
    # before inspecting the individual values.
    bound = clause.compile().params
    flat = [
        item
        for v in bound.values()
        for item in (v if isinstance(v, list) else [v])
    ]
    assert flat == ["120210000000000111"]


def test_equal_to_without_values_is_rejected():
    with pytest.raises(ChatwootHTTPException):
        _clause("equal_to", [])


def test_unknown_operator_is_rejected():
    with pytest.raises(ChatwootHTTPException):
        _clause("contains", [AD])
