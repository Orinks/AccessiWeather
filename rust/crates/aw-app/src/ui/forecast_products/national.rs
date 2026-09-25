//! National Products: the latest WPC, SPC, NHC and CPC AFOS text in tabs.
//! Port of `ui/dialogs/national_products_dialog.py`.

use std::rc::Rc;
use std::sync::Arc;

use aw_providers::products::tabs::{load_national_tab, NATIONAL_TABS};
use aw_providers::products::{ForecastProductService, ProductResult};
use wxdragon::prelude::*;

use super::panel::{PanelOptions, ProductPanel};
use super::{post_to_ui, Texts, WidgetSpec};

const TITLE: &str = "National Products";

pub(super) const WIDGETS: WidgetSpec = &[("Button#CLOSE", "&Close")];

/// `show_national_products_dialog`: modal, destroyed on close.
pub(crate) fn show_national_products_dialog(
    parent: &dyn WxWidget,
    service: Arc<ForecastProductService>,
) {
    let dialog = Dialog::builder(parent, TITLE)
        .with_style(DialogStyle::DefaultDialogStyle | DialogStyle::ResizeBorder)
        .build();
    let mut texts = Texts::new(WIDGETS);
    let main_sizer = BoxSizer::builder(Orientation::Vertical).build();
    let notebook = Notebook::builder(&dialog).build();

    let panels: Vec<Rc<ProductPanel>> = NATIONAL_TABS
        .iter()
        .enumerate()
        .map(|(index, &(product_id, label))| {
            let service = service.clone();
            let panel = ProductPanel::new(
                &notebook,
                PanelOptions {
                    product_type: product_id.to_string(),
                    loader: Arc::new(move || {
                        load_national_tab(&service, product_id).map(|p| ProductResult::One(Some(p)))
                    }),
                    cwa_office: Some("IEM".into()),
                    location_name: "National".into(),
                    on_availability: None,
                    advanced_lookup: None,
                    autoload: index == 0,
                },
            );
            notebook.add_page(&panel.panel, label, false, None);
            panel
        })
        .collect();
    main_sizer.add(&notebook, 1, SizerFlag::All | SizerFlag::Expand, 8);

    let button_sizer = BoxSizer::builder(Orientation::Horizontal).build();
    let close_button = Button::builder(&dialog)
        .with_id(ID_CLOSE)
        .with_label(texts.next("Button#CLOSE"))
        .build();
    button_sizer.add_stretch_spacer(1);
    button_sizer.add(&close_button, 0, SizerFlag::empty(), 0);
    main_sizer.add_sizer(&button_sizer, 0, SizerFlag::All | SizerFlag::Expand, 8);
    dialog.set_sizer(main_sizer, true);

    let panels = Rc::new(panels);
    close_button.on_click(move |e| {
        e.event.skip(false);
        dialog.end_modal(ID_CLOSE);
    });
    {
        let panels = panels.clone();
        notebook.on_page_changed(move |_| {
            let selected = usize::try_from(notebook.selection()).ok();
            if let Some(panel) = selected.and_then(|i| panels.get(i)) {
                panel.ensure_loaded();
            }
        });
    }
    dialog.bind_internal(EventType::CHAR_HOOK, move |e: Event| {
        if e.get_key_code() == Some(WXK_ESCAPE) {
            e.skip(false);
            dialog.close(false);
        } else {
            e.skip(true);
        }
    });

    dialog.set_size(Size::new(760, 620));
    dialog.centre();
    post_to_ui(move || notebook.set_focus());
    dialog.show_modal();
    for panel in panels.iter() {
        panel.close();
    }
    dialog.destroy();
}
