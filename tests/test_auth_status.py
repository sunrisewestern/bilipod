from src.bilipod.utils.auth_status import (
    clear_auth_status,
    get_auth_status,
    set_auth_status,
)


def test_auth_status_snapshot_contains_action():
    clear_auth_status()
    try:
        set_auth_status(
            state="action_required",
            message="Geetest login required.",
            action_label="Open Geetest login",
            action_url="https://example.com/login",
        )

        status = get_auth_status()

        assert status["state"] == "action_required"
        assert status["message"] == "Geetest login required."
        assert status["action_label"] == "Open Geetest login"
        assert status["action_url"] == "https://example.com/login"
        assert status["updated_at"] > 0
    finally:
        clear_auth_status()


def test_auth_status_clear_resets_to_idle():
    set_auth_status("complete", "Logged in.")

    clear_auth_status()
    status = get_auth_status()

    assert status["state"] == "idle"
    assert status["message"] == ""
    assert status["action_label"] is None
    assert status["action_url"] is None
