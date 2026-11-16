"""F13: the backend tags well-known error messages with a code the
dashboard translates; the English message stays as Chatwoot clients read it."""

from __future__ import annotations

from app.core.errors import with_error_code


def test_known_messages_get_a_code() -> None:
    assert with_error_code({"error": "Resource could not be found"}) == {
        "error": "Resource could not be found",
        "code": "not_found",
    }
    body = {"success": False, "errors": ["Invalid login credentials. Please try again."]}
    assert with_error_code(body)["code"] == "invalid_login"


def test_blank_and_taken_name_the_field() -> None:
    assert with_error_code({"message": "Phone number can't be blank"}) == {
        "message": "Phone number can't be blank",
        "code": "blank",
        "field": "phone_number",
    }
    tagged = with_error_code({"message": "Attribute key has already been taken for this model"})
    assert (tagged["code"], tagged["field"]) == ("taken", "attribute_key")


def test_existing_codes_and_unknown_messages_are_left_alone() -> None:
    body = {"errors": ["x"], "code": "too_many_attempts"}
    assert with_error_code(body) is body
    assert with_error_code({"message": "something else"}) == {"message": "something else"}
    assert with_error_code({"other": 1}) == {"other": 1}
