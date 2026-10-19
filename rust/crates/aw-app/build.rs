//! Platform link setup.
//!
//! * Windows: embed an application manifest (Common Controls v6, per-monitor
//!   DPI), the app icon and version information (Python's Nuitka build sets
//!   the same, with the nightly tag in the company name). prism loads the
//!   screen reader DLLs it needs at runtime, so none are linked here.
//! * Linux/macOS: prism is a shared library shipped beside the executable, so
//!   look for it there.

use embed_manifest::manifest::{ActiveCodePage, DpiAwareness, Setting, SupportedOS::*};
use embed_manifest::{embed_manifest, new_manifest};

fn main() {
    println!("cargo:rerun-if-changed=build.rs");
    println!("cargo:rerun-if-changed=ui/app.ico");
    println!("cargo:rerun-if-env-changed=ACCESSIWEATHER_BUILD_TAG");
    match std::env::var("CARGO_CFG_TARGET_OS").as_deref() {
        Ok("windows") => windows(),
        Ok("macos") => println!("cargo:rustc-link-arg=-Wl,-rpath,@executable_path"),
        Ok("linux") => println!("cargo:rustc-link-arg=-Wl,-rpath,$ORIGIN"),
        _ => {}
    }
}

fn windows() {
    let manifest = new_manifest("Orinks.AccessiWeather")
        .supported_os(Windows7..=Windows10)
        .active_code_page(ActiveCodePage::Utf8)
        .dpi_awareness(DpiAwareness::PerMonitorV2)
        .long_path_aware(Setting::Enabled);
    if let Err(e) = embed_manifest(manifest) {
        println!("cargo:warning=failed to embed Windows manifest: {e}");
    }

    let company = match std::env::var("ACCESSIWEATHER_BUILD_TAG") {
        Ok(tag) if !tag.is_empty() => format!("Orinks ({tag})"),
        _ => "Orinks".into(),
    };
    let mut resource = winresource::WindowsResource::new();
    resource
        .set_icon("ui/app.ico")
        .set("ProductName", "AccessiWeather")
        .set("FileDescription", "AccessiWeather")
        .set("CompanyName", &company)
        .set("OriginalFilename", "AccessiWeather.exe");
    if let Err(e) = resource.compile() {
        println!("cargo:warning=failed to embed the icon and version info: {e}");
    }
}
