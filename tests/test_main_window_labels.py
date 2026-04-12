from accessiweather.ui.main_window import QUICK_ACTION_LABELS


def test_quick_action_labels_match_visible_ui_copy():
    assert QUICK_ACTION_LABELS == {
        "add": "&Add Location",
        "remove": "&Remove Location",
        "refresh": "&Refresh Weather",
        "explain": "&Explain Weather",
        "discussion": "Forecast &Discussion",
        "settings": "&Settings",
    }
