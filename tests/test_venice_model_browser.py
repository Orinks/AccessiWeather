"""Provider isolation and truthful catalog filtering in the model browser."""

from types import SimpleNamespace
from unittest.mock import MagicMock

from accessiweather.api.venice_models import VeniceBalance, VeniceModel
from accessiweather.ui.dialogs.model_browser_dialog import ModelBrowserDialog
from accessiweather.ui.dialogs.settings_tabs.ai import AITab


def model(identifier="paid", prompt=1.0, completion=2.0, function=True):
    return VeniceModel(
        identifier,
        identifier,
        "Description",
        32000,
        prompt,
        completion,
        prompt == 0 and completion == 0,
        function,
        False,
    )


def browser():
    dialog = ModelBrowserDialog.__new__(ModelBrowserDialog)
    dialog.provider = "venice"
    dialog._announcer = MagicMock()
    dialog._closed = False
    for name in (
        "price_choice",
        "function_checkbox",
        "model_list",
        "select_btn",
        "description_text",
        "status_label",
        "refresh_btn",
        "balance_label",
    ):
        setattr(dialog, name, MagicMock())
    dialog.price_choice.GetSelection.return_value = 0
    dialog.function_checkbox.GetValue.return_value = False
    return dialog


def test_price_and_function_filters_keep_unknown_prices_out_of_free_and_paid():
    dialog = browser()
    models = [
        model(),
        model("free", 0, 0),
        model("unknown", None, None),
        model("no-tools", function=False),
    ]
    assert all(dialog._matches_price_and_capability(item) for item in models)
    dialog.price_choice.GetSelection.return_value = 1
    assert [m.id for m in models if dialog._matches_price_and_capability(m)] == ["free"]
    dialog.price_choice.GetSelection.return_value = 2
    assert [m.id for m in models if dialog._matches_price_and_capability(m)] == ["paid", "no-tools"]
    dialog.function_checkbox.GetValue.return_value = True
    assert [m.id for m in models if dialog._matches_price_and_capability(m)] == ["paid"]


def test_prices_show_input_output_and_unknown_without_calling_unknown_free():
    assert ModelBrowserDialog._model_pricing(model()) == "Input: $1; output: $2 per million tokens"
    unknown = ModelBrowserDialog._model_pricing(model(prompt=None))
    assert "Input: unknown" in unknown
    assert "Free" not in unknown


def test_credit_status_uses_permission_not_positive_balance():
    status = ModelBrowserDialog._balance_status
    assert "unknown" in status(VeniceBalance(None, "USD", 10, None))
    assert "cannot currently consume" in status(VeniceBalance(False, "USD", 10, None))
    assert "No API credits" in status(VeniceBalance(False, "USD", 0, 0))
    assert "does not guarantee" in status(VeniceBalance(True, "USD", 10, None))
    assert "USD: $10" in status(VeniceBalance(True, "USD", 10, None))
    assert "DIEM:" not in status(VeniceBalance(True, "USD", 10, None))
    assert "Consumption currency: DIEM" in status(VeniceBalance(True, "DIEM", None, 3))
    assert "DIEM: 3" in status(VeniceBalance(True, "DIEM", None, 3))
    assert "USD:" not in status(VeniceBalance(True, "DIEM", None, 3))


def test_offline_model_cannot_be_selected_or_double_clicked(monkeypatch):
    import wx

    monkeypatch.setattr(wx, "NOT_FOUND", -1, raising=False)
    dialog = browser()
    offline = model()
    offline.offline = True
    dialog._filtered_models = [offline]
    dialog.model_list.GetSelection.return_value = 0
    dialog.EndModal = MagicMock()
    dialog._on_model_selected(None)
    assert dialog.get_selected_model_id() is None
    dialog.select_btn.Enable.assert_called_with(False)
    assert "offline and unavailable" in dialog.description_text.SetValue.call_args.args[0]
    dialog._on_model_double_click(None)
    dialog.EndModal.assert_not_called()
    dialog._on_select(None)
    assert "offline and unavailable" in dialog._announcer.announce.call_args.args[0]


def test_load_completion_announces_count_and_credit_status_together():
    dialog = browser()
    dialog._load_generation = 1
    dialog.api_key = None
    dialog.IsBeingDeleted = lambda: False
    dialog.Layout = MagicMock()
    dialog._on_models_loaded = MagicMock()
    dialog.status_label.GetLabel.return_value = "12 models available"
    dialog.balance_label.GetLabel.return_value = "Add a Venice API key to check account credits."
    dialog._finish_load(1, [], None, None)
    dialog._announcer.announce.assert_called_once_with(
        "12 models available. Add a Venice API key to check account credits."
    )


def test_discrete_filter_announces_count_but_search_does_not():
    dialog = browser()
    dialog.free_only_checkbox = MagicMock()
    dialog._update_provider_list = MagicMock()
    dialog._apply_filters = MagicMock()
    dialog.status_label.GetLabel.return_value = "Showing 5 of 12 models"
    dialog._on_filter_changed(MagicMock())
    dialog._announcer.announce.assert_called_once_with("Showing 5 of 12 models")
    dialog._announcer.announce.reset_mock()
    dialog._on_search_changed(None)
    dialog._announcer.announce.assert_not_called()


def test_list_labels_include_assistant_compatibility():
    dialog = browser()
    dialog._all_models = [model(), model("no-tools", function=False)]
    dialog._filtered_models = dialog._all_models
    dialog._populate_list()
    labels = [call.args[0] for call in dialog.model_list.Append.call_args_list]
    assert "Weather assistant compatible" in labels[0]
    assert "Explanations only" in labels[1]


def test_shutdown_releases_announcer_only_once():
    dialog = browser()
    dialog._shutdown()
    dialog._shutdown()
    assert dialog._closed
    dialog._announcer.shutdown.assert_called_once()


def test_paid_model_is_selectable_without_account_credit_gate(monkeypatch):
    import wx

    monkeypatch.setattr(wx, "NOT_FOUND", -1, raising=False)
    dialog = browser()
    dialog._filtered_models = [model()]
    dialog.model_list.GetSelection.return_value = 0
    dialog._on_model_selected(None)
    assert dialog.get_selected_model_id() == "paid"
    dialog.select_btn.Enable.assert_called_once_with(True)


def test_closed_or_superseded_load_cannot_update_controls():
    dialog = browser()
    dialog._closed = True
    dialog._load_generation = 2
    dialog._finish_load(2, [model()], None, None)
    dialog._closed = False
    dialog._finish_load(1, [model()], None, None)
    dialog.refresh_btn.Enable.assert_not_called()


def test_filter_repopulation_clears_stale_selection():
    dialog = browser()
    dialog._all_models = [model()]
    dialog._filtered_models = []
    dialog._selected_model_id = "paid"
    dialog._populate_list()
    assert dialog.get_selected_model_id() is None
    dialog.select_btn.Enable.assert_called_once_with(False)


def test_venice_browse_uses_only_venice_key_and_updates_only_venice_model(monkeypatch):
    from accessiweather.ui.dialogs import model_browser_dialog

    show = MagicMock(return_value="chosen-venice")
    monkeypatch.setattr(model_browser_dialog, "show_model_browser_dialog", show)
    controls = {
        name: MagicMock() for name in ("venice_key", "venice_model", "openrouter_key", "ai_model")
    }
    controls["venice_key"].GetValue.return_value = "venice-test-key"
    dialog = SimpleNamespace(_controls=controls)
    AITab(dialog)._on_browse_venice_models(None)
    show.assert_called_once_with(dialog, api_key="venice-test-key", provider="venice")
    controls["venice_model"].SetValue.assert_called_once_with("chosen-venice")
    assert not controls["openrouter_key"].mock_calls
    assert not controls["ai_model"].mock_calls
