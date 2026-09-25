//! Release packaging: `installer/build_nuitka.py` (stage the build and its
//! runtime files), `installer/build.py` (installer, portable archives) and
//! `installer/build_appimage.py`.
//!
//! Everything lands in `rust/dist/` under the Python build's file names; the
//! release job renames them to the release asset names both editions'
//! updaters look for (`AccessiWeather-<version>-windows-setup.exe`, ...).
//! Each artifact gets a `<name>.sha256` beside it.

use std::fs;
use std::io::Write;
use std::path::{Path, PathBuf};
use std::process::Command;

use sha2::{Digest, Sha256};

use crate::{repo_root, run_checked, rust_dir, Result, VERSION};

#[derive(Clone, Copy, PartialEq, Eq, Debug, clap::ValueEnum)]
pub enum Artifact {
    /// Inno Setup installer, AccessiWeather_Setup_v<version>.exe
    WindowsSetup,
    /// Portable zip, AccessiWeather_Portable_v<version>.zip
    WindowsPortable,
    /// Zipped app bundle, AccessiWeather_macOS_v<version>.zip
    Macos,
    /// Disk image, AccessiWeather_v<version>.dmg
    MacosDmg,
    /// Tarball, AccessiWeather_Linux_v<version>.tar.gz
    Linux,
    /// AppImage, AccessiWeather_Linux_v<version>_x86_64.AppImage
    LinuxAppimage,
}

impl Artifact {
    fn os(self) -> &'static str {
        match self {
            Self::WindowsSetup | Self::WindowsPortable => "windows",
            Self::Macos | Self::MacosDmg => "macos",
            Self::Linux | Self::LinuxAppimage => "linux",
        }
    }
}

/// The Visual C++ runtime the executable imports. Shipped beside it, as
/// the Python build does: machines without the redistributable need them,
/// and they replace the older copies a Python install leaves in the folder.
const VC_RUNTIME: [&str; 4] = [
    "vcruntime140.dll",
    "vcruntime140_1.dll",
    "msvcp140.dll",
    "msvcp140_atomic_wait.dll",
];
const PORTABLE_SOUNDPACK_DIR: &str = "data/soundpacks/default";

pub fn run(artifacts: &[Artifact]) -> Result<()> {
    let os = std::env::consts::OS;
    let artifacts: Vec<Artifact> = if artifacts.is_empty() {
        <Artifact as clap::ValueEnum>::value_variants()
            .iter()
            .copied()
            .filter(|a| a.os() == os)
            .collect()
    } else {
        artifacts.to_vec()
    };
    if let Some(a) = artifacts.iter().find(|a| a.os() != os) {
        return Err(format!("{a:?} can only be built on {}", a.os()).into());
    }
    eprintln!("AccessiWeather {VERSION} packaging: {artifacts:?}");

    run_checked(
        Command::new(std::env::var("CARGO").unwrap_or_else(|_| "cargo".into()))
            .args(["build", "--release", "-p", "accessiweather"])
            .current_dir(rust_dir()),
    )?;
    let dist = rust_dir().join("dist");
    fs::create_dir_all(&dist)?;
    let staged = match os {
        "windows" => stage_windows(&dist)?,
        "macos" => stage_macos(&dist)?,
        _ => stage_linux(&dist)?,
    };
    for artifact in artifacts {
        let path = match artifact {
            Artifact::WindowsSetup => windows_installer(&staged, &dist)?,
            Artifact::WindowsPortable => windows_portable_zip(&staged, &dist)?,
            Artifact::Macos => macos_zip(&staged, &dist)?,
            Artifact::MacosDmg => macos_dmg(&staged, &dist)?,
            Artifact::Linux => linux_tarball(&staged, &dist)?,
            Artifact::LinuxAppimage => appimage(&staged, &dist)?,
        };
        write_sha256(&path)?;
        eprintln!("OK: {}", path.display());
    }
    Ok(())
}

fn target_dir() -> Result<PathBuf> {
    Ok(match std::env::var_os("CARGO_TARGET_DIR") {
        Some(dir) => std::env::current_dir()?.join(dir),
        None => rust_dir().join("target"),
    })
}

fn release_binary() -> Result<PathBuf> {
    let name = format!("accessiweather{}", std::env::consts::EXE_SUFFIX);
    Ok(target_dir()?.join("release").join(name))
}

fn icon(name: &str) -> PathBuf {
    crate::icons::icon_dir().join(name)
}

fn fresh_dir(dir: &Path) -> Result<()> {
    if dir.exists() {
        fs::remove_dir_all(dir)?;
    }
    fs::create_dir_all(dir)?;
    Ok(())
}

/// Copy `src` into `dst` recursively, keeping symlinks as symlinks.
fn copy_dir(src: &Path, dst: &Path) -> Result<()> {
    fs::create_dir_all(dst)?;
    for entry in fs::read_dir(src)? {
        let entry = entry?;
        let (from, to) = (entry.path(), dst.join(entry.file_name()));
        let kind = entry.file_type()?;
        if kind.is_symlink() {
            copy_symlink(&from, &to)?;
        } else if kind.is_dir() {
            copy_dir(&from, &to)?;
        } else {
            fs::copy(&from, &to)?;
        }
    }
    Ok(())
}

#[cfg(unix)]
fn copy_symlink(from: &Path, to: &Path) -> Result<()> {
    std::os::unix::fs::symlink(fs::read_link(from)?, to)?;
    Ok(())
}

#[cfg(not(unix))]
fn copy_symlink(from: &Path, to: &Path) -> Result<()> {
    fs::copy(from, to)?;
    Ok(())
}

#[cfg(unix)]
fn make_executable(path: &Path) -> Result<()> {
    use std::os::unix::fs::PermissionsExt;
    fs::set_permissions(path, fs::Permissions::from_mode(0o755))?;
    Ok(())
}

#[cfg(not(unix))]
fn make_executable(_path: &Path) -> Result<()> {
    Ok(())
}

/// The repository's default sound pack, bundled as `soundpacks/default`.
fn copy_default_soundpack(soundpacks: &Path) -> Result<()> {
    let source = repo_root().join("soundpacks").join("default");
    if !source.join("pack.json").exists() {
        return Err(format!("default sound pack not found at {}", source.display()).into());
    }
    copy_dir(&source, &soundpacks.join("default"))
}

/// prism's shared library (Linux/macOS link it dynamically; Windows statically).
fn copy_prism(dest: &Path) -> Result<()> {
    let build = target_dir()?.join("release").join("build");
    let mut copied = false;
    for entry in fs::read_dir(&build)? {
        let crate_dir = entry?.path();
        let is_prism = crate_dir
            .file_name()
            .is_some_and(|n| n.to_string_lossy().starts_with("prism-sys-"));
        let lib = crate_dir.join("out").join("lib");
        if !is_prism || !lib.is_dir() {
            continue;
        }
        for file in fs::read_dir(&lib)? {
            let file = file?;
            let name = file.file_name().to_string_lossy().into_owned();
            if name.starts_with("libprism") && (name.contains(".so") || name.ends_with(".dylib")) {
                let to = dest.join(&name);
                if !to.exists() {
                    if file.file_type()?.is_symlink() {
                        copy_symlink(&file.path(), &to)?;
                    } else {
                        fs::copy(file.path(), &to)?;
                    }
                }
                copied = true;
            }
        }
    }
    if !copied {
        return Err(format!("no prism library under {}", build.display()).into());
    }
    Ok(())
}

fn readme(dest: &Path) -> Result<()> {
    fs::copy(rust_dir().join("packaging/README-portable.txt"), dest)?;
    Ok(())
}

// Windows ---------------------------------------------------------------------

/// `dist/AccessiWeather_dir`: the installer's payload.
fn stage_windows(dist: &Path) -> Result<PathBuf> {
    let stage = dist.join("AccessiWeather_dir");
    fresh_dir(&stage)?;
    fs::copy(release_binary()?, stage.join("AccessiWeather.exe"))?;
    let system32 = PathBuf::from(std::env::var_os("SystemRoot").unwrap_or("C:\\Windows".into()))
        .join("System32");
    for dll in VC_RUNTIME {
        fs::copy(system32.join(dll), stage.join(dll))
            .map_err(|e| format!("{}: {e}", system32.join(dll).display()))?;
    }
    copy_default_soundpack(&stage.join("soundpacks"))?;
    Ok(stage)
}

fn find_iscc() -> PathBuf {
    [
        r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
        r"C:\Program Files\Inno Setup 6\ISCC.exe",
    ]
    .into_iter()
    .map(PathBuf::from)
    .find(|p| p.exists())
    .unwrap_or_else(|| "iscc".into())
}

fn windows_installer(staged: &Path, dist: &Path) -> Result<PathBuf> {
    let out = dist.join(format!("AccessiWeather_Setup_v{VERSION}.exe"));
    let iss = rust_dir().join("packaging/windows/accessiweather.iss");
    run_checked(
        Command::new(find_iscc())
            .arg(format!("/DMyAppVersion={VERSION}"))
            .arg(format!("/DStageDir={}", staged.display()))
            .arg(format!("/DOutputDir={}", dist.display()))
            .arg(&iss),
    )?;
    Ok(out)
}

/// Python's portable rules: a `.portable` marker, an empty `config` folder
/// and the default sound pack under `data/soundpacks/default`, all inside
/// an `AccessiWeather` folder in the zip.
fn windows_portable_zip(staged: &Path, dist: &Path) -> Result<PathBuf> {
    let root = dist.join("AccessiWeather");
    fresh_dir(&root)?;
    copy_dir(staged, &root)?;
    readme(&root.join("README.txt"))?;
    fs::write(root.join(".portable"), "1\n")?;
    fs::create_dir_all(root.join("config"))?;
    copy_dir(
        &root.join("soundpacks").join("default"),
        &root.join(PORTABLE_SOUNDPACK_DIR),
    )?;

    let out = dist.join(format!("AccessiWeather_Portable_v{VERSION}.zip"));
    let mut zip = zip::ZipWriter::new(fs::File::create(&out)?);
    let options = zip::write::SimpleFileOptions::default()
        .compression_method(zip::CompressionMethod::Deflated);
    add_to_zip(&mut zip, &root, "AccessiWeather", options)?;
    zip.finish()?;

    let names: Vec<String> = zip::ZipArchive::new(fs::File::open(&out)?)?
        .file_names()
        .map(str::to_string)
        .collect();
    let manifest = format!("{PORTABLE_SOUNDPACK_DIR}/pack.json");
    if !names
        .iter()
        .any(|n| n == &manifest || n.split_once('/').is_some_and(|(_, rest)| rest == manifest))
    {
        return Err(format!(
            "Portable ZIP is missing default/pack.json at the expected portable path ({manifest}) in {}",
            out.display()
        )
        .into());
    }
    Ok(out)
}

fn add_to_zip(
    zip: &mut zip::ZipWriter<fs::File>,
    dir: &Path,
    prefix: &str,
    options: zip::write::SimpleFileOptions,
) -> Result<()> {
    zip.add_directory(format!("{prefix}/"), options)?;
    let mut entries: Vec<_> = fs::read_dir(dir)?.collect::<std::io::Result<_>>()?;
    entries.sort_by_key(|e| e.file_name());
    for entry in entries {
        let name = format!("{prefix}/{}", entry.file_name().to_string_lossy());
        if entry.file_type()?.is_dir() {
            add_to_zip(zip, &entry.path(), &name, options)?;
        } else {
            zip.start_file(name, options)?;
            std::io::copy(&mut fs::File::open(entry.path())?, zip)?;
        }
    }
    Ok(())
}

// macOS -----------------------------------------------------------------------

/// `dist/AccessiWeather.app`, ad-hoc signed (Gatekeeper users need
/// right-click > Open until there is a Developer ID).
fn stage_macos(dist: &Path) -> Result<PathBuf> {
    let app = dist.join("AccessiWeather.app");
    fresh_dir(&app)?;
    let (macos, resources) = (app.join("Contents/MacOS"), app.join("Contents/Resources"));
    fs::create_dir_all(&macos)?;
    fs::create_dir_all(&resources)?;
    fs::copy(release_binary()?, macos.join("AccessiWeather"))?;
    copy_prism(&macos)?;
    let plist = fs::read_to_string(rust_dir().join("packaging/macos/Info.plist"))?;
    fs::write(
        app.join("Contents/Info.plist"),
        plist.replace("@VERSION@", VERSION),
    )?;
    fs::copy(icon("app.icns"), resources.join("app.icns"))?;
    copy_default_soundpack(&resources.join("soundpacks"))?;
    let signed = run_checked(
        Command::new("codesign")
            .args(["--force", "--deep", "--sign", "-"])
            .arg(&app),
    );
    if let Err(e) = signed {
        eprintln!("ad-hoc codesign unavailable ({e}); shipping unsigned");
    }
    Ok(app)
}

fn macos_zip(app: &Path, dist: &Path) -> Result<PathBuf> {
    let out = dist.join(format!("AccessiWeather_macOS_v{VERSION}.zip"));
    remove_file_if_exists(&out)?;
    run_checked(
        Command::new("ditto")
            .args(["-c", "-k", "--keepParent"])
            .arg(app)
            .arg(&out),
    )?;
    Ok(out)
}

/// `create_macos_dmg`'s hdiutil path: the app beside an Applications link.
/// Python's macOS updater installs from a disk image, so this is what moves
/// Python Mac users onto this edition.
fn macos_dmg(app: &Path, dist: &Path) -> Result<PathBuf> {
    let out = dist.join(format!("AccessiWeather_v{VERSION}.dmg"));
    remove_file_if_exists(&out)?;
    let temp = dist.join("dmg_temp");
    fresh_dir(&temp)?;
    run_checked(
        Command::new("ditto")
            .arg(app)
            .arg(temp.join("AccessiWeather.app")),
    )?;
    #[cfg(unix)]
    std::os::unix::fs::symlink("/Applications", temp.join("Applications"))?;
    // hdiutil intermittently fails with "Resource busy" on CI runners.
    let mut attempt = 1;
    while let Err(e) = run_checked(
        Command::new("hdiutil")
            .args(["create", "-volname", "AccessiWeather", "-srcfolder"])
            .arg(&temp)
            .args(["-ov", "-format", "UDZO"])
            .arg(&out),
    ) {
        if attempt == 3 {
            return Err(e);
        }
        attempt += 1;
        std::thread::sleep(std::time::Duration::from_secs(5));
    }
    fs::remove_dir_all(&temp)?;
    Ok(out)
}

// Linux -----------------------------------------------------------------------

/// `dist/AccessiWeather`: the tarball's folder and the AppImage payload.
fn stage_linux(dist: &Path) -> Result<PathBuf> {
    let stage = dist.join("AccessiWeather");
    fresh_dir(&stage)?;
    fs::copy(release_binary()?, stage.join("AccessiWeather"))?;
    copy_prism(&stage)?;
    copy_default_soundpack(&stage.join("soundpacks"))?;
    fs::copy(
        rust_dir().join("packaging/linux/accessiweather.desktop"),
        stage.join("accessiweather.desktop"),
    )?;
    fs::copy(icon("app_256.png"), stage.join("accessiweather.png"))?;
    readme(&stage.join("README.txt"))?;
    Ok(stage)
}

fn linux_tarball(stage: &Path, dist: &Path) -> Result<PathBuf> {
    let out = dist.join(format!("AccessiWeather_Linux_v{VERSION}.tar.gz"));
    let gz = flate2::write::GzEncoder::new(fs::File::create(&out)?, flate2::Compression::default());
    let mut tar = tar::Builder::new(gz);
    tar.follow_symlinks(false);
    tar.append_dir_all("AccessiWeather", stage)?;
    tar.into_inner()?.finish()?;
    Ok(out)
}

const LINUXDEPLOY_URL: &str = "https://github.com/linuxdeploy/linuxdeploy/releases/download/1-alpha-20251107-1/linuxdeploy-x86_64.AppImage";
const APPIMAGE_RUNTIME_URL: &str =
    "https://github.com/AppImage/type2-runtime/releases/download/20251108/runtime-x86_64";

/// Libraries that must come from the target system, not the AppImage.
const EXCLUDED_LIBRARY_GLOBS: &[&str] = &[
    // GLib/GIO: host gio modules (GVFS, etc.) load into whichever GLib is in
    // the process; shipping our own triggers duplicate-GType registration
    // crashes ("cannot register existing type 'GTask'").
    "libglib-2.0*",
    "libgio-2.0*",
    "libgobject-2.0*",
    "libgmodule-2.0*",
    "libgthread-2.0*",
    // GTK/desktop + accessibility stack: must be the host's so AT-SPI (screen
    // readers), themes, and input methods work.
    "libgtk-3*",
    "libgdk-3*",
    "libgdk_pixbuf-2.0*",
    "libpango*",
    "libcairo*",
    "libpixman*",
    "libatk*",
    "libatspi*",
    "libnotify*",
    "libthai*",
    "libdatrie*",
    "libfribidi*",
    "libgraphite2*",
    "libharfbuzz*",
    // Host system plumbing tied to the running OS.
    "libdbus-1*",
    "libsystemd*",
    "libselinux*",
    "libcap*",
    "libmount*",
    "libblkid*",
    "liblz4*",
    "libgcrypt*",
    "libgpg-error*",
    // TLS/HTTP: use the distro's security-patched OpenSSL/curl stack.
    "libssl*",
    "libcrypto*",
    "libcurl*",
    "libgnutls*",
    "libnettle*",
    "libhogweed*",
    "libtasn1*",
    "libp11-kit*",
    "libidn2*",
    "libunistring*",
    "libpsl*",
    "libnghttp2*",
    "libssh*",
    "librtmp*",
    "liblber*",
    "libldap*",
    "libsasl2*",
    "libgssapi_krb5*",
    "libkrb5*",
    "libk5crypto*",
    "libkeyutils*",
];

/// Sonames that must never appear in usr/lib (hard failures, like the
/// tarball's OpenSSL check).
const FORBIDDEN_BUNDLED_PREFIXES: &[&str] = &[
    "libssl",
    "libcrypto",
    "libglib-2.0",
    "libgio-2.0",
    "libgobject-2.0",
    "libgtk-3",
    "libgdk-3",
    "libatk",
    "libatspi",
];

/// Ubuntu sonames that other distros name differently (Fedora ships
/// libjpeg.so.62), so the AppImage must carry them whenever the binary
/// links them (wxWidgets' image handlers).
const REQUIRED_BUNDLED_SONAMES: &[&str] = &["libjpeg.so.8", "libtiff.so.6"];

/// Download `url` to `target` with simple retries; keep an existing file.
fn download(url: &str, target: &Path) -> Result<()> {
    if fs::metadata(target).is_ok_and(|m| m.len() > 0) {
        return Ok(());
    }
    fs::create_dir_all(target.parent().expect("download target has a folder"))?;
    let client = reqwest::blocking::Client::builder()
        .timeout(std::time::Duration::from_secs(120))
        .build()?;
    let attempts = 4;
    for attempt in 1..=attempts {
        eprintln!("Downloading {url} (attempt {attempt})");
        let result = client
            .get(url)
            .send()
            .and_then(|r| r.error_for_status())
            .and_then(|r| r.bytes())
            .map_err(|e| e.to_string())
            .and_then(|b| {
                if b.is_empty() {
                    Err("downloaded file is empty".to_string())
                } else {
                    Ok(b)
                }
            });
        match result {
            Ok(bytes) => {
                fs::write(target, &bytes)?;
                return Ok(());
            }
            Err(e) if attempt == attempts => {
                return Err(format!("Failed to download {url}: {e}").into())
            }
            Err(_) => std::thread::sleep(std::time::Duration::from_secs(5 * attempt)),
        }
    }
    unreachable!("the last attempt returns")
}

/// linuxdeploy bundles the shared libraries the binary needs that other
/// distros lack, while the host-integration stacks above stay excluded so
/// the app keeps using the target system's GTK, GLib, D-Bus and OpenSSL.
fn appimage(stage: &Path, dist: &Path) -> Result<PathBuf> {
    let work = target_dir()?.join("appimage");
    fresh_dir(&work)?;
    let linuxdeploy = work.join("tools/linuxdeploy-x86_64.AppImage");
    download(LINUXDEPLOY_URL, &linuxdeploy)?;
    make_executable(&linuxdeploy)?;
    let runtime = work.join("tools/runtime-x86_64");
    download(APPIMAGE_RUNTIME_URL, &runtime)?;

    let appdir = work.join("AppDir");
    let payload = appdir.join("opt/accessiweather");
    eprintln!("Copying {} into AppDir", stage.display());
    copy_dir(stage, &payload)?;
    fs::copy(icon("app_256.png"), work.join("accessiweather.png"))?;

    let linux = rust_dir().join("packaging/linux");
    let mut cmd = Command::new(&linuxdeploy);
    cmd.arg("--appimage-extract-and-run")
        .arg(format!("--appdir={}", appdir.display()))
        .arg(format!("--deploy-deps-only={}", payload.display()))
        .arg(format!(
            "--desktop-file={}",
            linux.join("accessiweather.desktop").display()
        ))
        .arg(format!(
            "--icon-file={}",
            work.join("accessiweather.png").display()
        ))
        .arg(format!(
            "--custom-apprun={}",
            linux.join("AppRun").display()
        ))
        .arg("--output=appimage")
        .args(
            EXCLUDED_LIBRARY_GLOBS
                .iter()
                .map(|g| format!("--exclude-library={g}")),
        )
        .env("LINUXDEPLOY_OUTPUT_VERSION", VERSION)
        .env("LDAI_RUNTIME_FILE", &runtime)
        .current_dir(&work);
    run_checked(&mut cmd)?;

    let produced = fs::read_dir(&work)?
        .filter_map(|e| e.ok().map(|e| e.path()))
        .filter(|p| p.extension().is_some_and(|x| x == "AppImage"))
        .max_by_key(|p| fs::metadata(p).and_then(|m| m.modified()).ok())
        .ok_or("linuxdeploy did not produce an AppImage")?;
    verify_bundled_libraries(&appdir.join("usr/lib"), &payload.join("AccessiWeather"))?;

    let out = dist.join(format!("AccessiWeather_Linux_v{VERSION}_x86_64.AppImage"));
    remove_file_if_exists(&out)?;
    fs::copy(&produced, &out)?;
    fs::remove_file(&produced)?;
    make_executable(&out)?;
    Ok(out)
}

/// The sonames `binary` links directly (`objdump -p`'s NEEDED entries).
fn needed_libraries(binary: &Path) -> Result<Vec<String>> {
    let output = Command::new("objdump").arg("-p").arg(binary).output()?;
    if !output.status.success() {
        return Err(format!("objdump -p {} failed", binary.display()).into());
    }
    Ok(String::from_utf8_lossy(&output.stdout)
        .lines()
        .filter_map(|l| l.trim().strip_prefix("NEEDED"))
        .map(|soname| soname.trim().to_string())
        .collect())
}

/// Fail when usr/lib bundles host stacks or misses portability libraries.
fn verify_bundled_libraries(lib_dir: &Path, binary: &Path) -> Result<()> {
    let bundled: Vec<String> = fs::read_dir(lib_dir)
        .map(|entries| {
            entries
                .filter_map(|e| e.ok())
                .map(|e| e.file_name().to_string_lossy().into_owned())
                .collect()
        })
        .unwrap_or_default();
    let mut forbidden: Vec<&String> = bundled
        .iter()
        .filter(|name| {
            FORBIDDEN_BUNDLED_PREFIXES
                .iter()
                .any(|p| name.starts_with(p))
        })
        .collect();
    forbidden.sort();
    if !forbidden.is_empty() {
        return Err(format!(
            "AppImage must not bundle host-integration libraries \
             (GLib/GTK/OpenSSL stay on the target system): {forbidden:?}"
        )
        .into());
    }
    let needed = needed_libraries(binary)?;
    let missing: Vec<&str> = REQUIRED_BUNDLED_SONAMES
        .iter()
        .copied()
        .filter(|soname| needed.iter().any(|n| n == soname))
        .filter(|soname| !bundled.iter().any(|b| b == soname))
        .collect();
    if !missing.is_empty() {
        return Err(format!(
            "AppImage is missing libraries needed on non-Debian distros: {missing:?}"
        )
        .into());
    }
    eprintln!("Verified {} bundled libraries in usr/lib", bundled.len());
    Ok(())
}

fn remove_file_if_exists(path: &Path) -> Result<()> {
    match fs::remove_file(path) {
        Err(e) if e.kind() != std::io::ErrorKind::NotFound => Err(e.into()),
        _ => Ok(()),
    }
}

/// `<name>.sha256` in `sha256sum` format.
fn write_sha256(path: &Path) -> Result<()> {
    let mut hasher = Sha256::new();
    std::io::copy(&mut fs::File::open(path)?, &mut hasher)?;
    let name = path
        .file_name()
        .expect("artifact has a name")
        .to_string_lossy();
    let mut sum = fs::File::create(format!("{}.sha256", path.display()))?;
    writeln!(sum, "{:x}  {name}", hasher.finalize())?;
    Ok(())
}
