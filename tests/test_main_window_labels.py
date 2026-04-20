from accessiweather.ui.main_window import QUICK_ACTION_LABELS


def test_quick_action_labels_match_visible_ui_copy():
    assert QUICK_ACTION_LABELS == {
        "add": "&Add Location",
        "edit": "&Edit Location",
        "remove": "&Remove Location",
        "refresh": "Re&fresh Weather",
        "explain": "Explain &Conditions",
        "discussion": "Forecaster &Notes",
        "settings": "&Settings",
    }


def test_quick_action_labels_use_unique_access_keys():
    access_keys = [label[label.index("&") + 1].lower() for label in QUICK_ACTION_LABELS.values()]
    assert len(access_keys) == len(set(access_keys))
