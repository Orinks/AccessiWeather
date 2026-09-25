//! Platform link setup.
//!
//! * Windows: embed an application manifest (Common Controls v6, per-monitor
//!   DPI) and delay-load the screen reader DLLs that the statically linked
//!   prism imports, since most machines don't have all of them.
//! * Linux/macOS: prism is a shared library shipped beside the executable, so
//!   look for it there.

use embed_manifest::manifest::{ActiveCodePage, DpiAwareness, Setting, SupportedOS::*};
use embed_manifest::{embed_manifest, new_manifest};

fn main() {
    println!("cargo:rerun-if-changed=build.rs");
    match std::env::var("CARGO_CFG_TARGET_OS").as_deref() {
        Ok("windows") => windows(),
        Ok("macos") => println!("cargo:rustc-link-arg=-Wl,-rpath,@executable_path"),
        Ok("linux") => println!("cargo:rustc-link-arg=-Wl,-rpath,$ORIGIN"),
        _ => {}
    }
}

fn windows() {
    if let Ok(dlls) = std::env::var("DEP_PRISMER_DELAY_LOAD_DLLS") {
        for dll in dlls.split(';').filter(|dll| !dll.is_empty()) {
            println!("cargo:rustc-link-arg=/DELAYLOAD:{dll}");
        }
        // Bridges for other platforms have no imports here; LNK4199 is expected.
        println!("cargo:rustc-link-arg=/IGNORE:4199");
        // prism's failure hook substitutes stubs for screen reader DLLs that
        // aren't installed. Pull it in explicitly, or delayimp.lib's empty
        // default wins and probing a missing reader crashes the process.
        println!("cargo:rustc-link-arg=/INCLUDE:__pfnDliFailureHook2");
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
