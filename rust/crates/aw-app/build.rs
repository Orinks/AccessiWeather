//! Embed a Windows application manifest so wxWidgets gets Common Controls v6
//! (themed controls, no "manifest is missing" warning box) and per-monitor DPI.

use embed_manifest::manifest::{ActiveCodePage, DpiAwareness, Setting, SupportedOS::*};
use embed_manifest::{embed_manifest, new_manifest};

fn main() {
    println!("cargo:rerun-if-changed=build.rs");
    let target = std::env::var("TARGET").unwrap_or_default();
    if !target.contains("windows") {
        return;
    }
    let manifest = new_manifest("Orinks.AccessiWeather")
        .supported_os(Windows7..=Windows10)
        .active_code_page(ActiveCodePage::Utf8)
        .dpi_awareness(DpiAwareness::PerMonitorV2)
        .long_path_aware(Setting::Enabled);
    if let Err(e) = embed_manifest(manifest) {
        println!("cargo:warning=failed to embed Windows manifest: {e}");
    }
}
