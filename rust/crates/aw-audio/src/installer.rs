//! Sound pack ZIP installation (`notifications/sound_pack_installer.py`).
//!
//! Only `safe_extractall` and `SoundPackInstaller.install_from_zip` are
//! reachable in the Python app (the community browser installs with it);
//! the installer's uninstall/export/list/template helpers are unused there
//! and not ported. The Sound Pack Manager's own import/export live in
//! [`crate::manager`].

use std::fs;
use std::io;
use std::path::{Component, Path, PathBuf};

use serde_json::Value;

use crate::pack::read_json;
use crate::py::{py_str, py_type_name};

/// Resolve `member` inside `target` without touching the file system, or
/// `None` when it would escape (`..`, absolute or drive paths).
pub(crate) fn contained_path(target: &Path, member: &str) -> Option<PathBuf> {
    let mut out = target.to_path_buf();
    let mut depth = 0usize;
    for component in Path::new(member).components() {
        match component {
            Component::Normal(part) => {
                out.push(part);
                depth += 1;
            }
            Component::CurDir => {}
            Component::ParentDir if depth > 0 => {
                out.pop();
                depth -= 1;
            }
            _ => return None,
        }
    }
    Some(out)
}

/// `safe_extractall`: extract every member, refusing the whole archive when
/// any member would land outside `target_dir` (Zip Slip).
pub fn safe_extractall<R: io::Read + io::Seek>(
    zip: &mut zip::ZipArchive<R>,
    target_dir: &Path,
) -> Result<(), String> {
    let names: Vec<String> = zip.file_names().map(str::to_string).collect();
    for name in &names {
        if contained_path(target_dir, name).is_none() {
            return Err(format!(
                "Zip Slip detected: member '{name}' would extract outside target directory"
            ));
        }
    }
    for i in 0..zip.len() {
        let mut member = zip.by_index(i).map_err(|e| e.to_string())?;
        let Some(dest) = contained_path(target_dir, member.name()) else {
            continue;
        };
        if member.is_dir() {
            fs::create_dir_all(&dest).map_err(|e| e.to_string())?;
            continue;
        }
        if let Some(parent) = dest.parent() {
            fs::create_dir_all(parent).map_err(|e| e.to_string())?;
        }
        let mut out = fs::File::create(&dest).map_err(|e| e.to_string())?;
        io::copy(&mut member, &mut out).map_err(|e| e.to_string())?;
    }
    Ok(())
}

/// `Path.rglob("pack.json")`'s first hit: the root, then each directory's
/// children in a top-down walk.
fn find_pack_json(root: &Path) -> Option<PathBuf> {
    let direct = root.join("pack.json");
    if direct.exists() {
        return Some(direct);
    }
    let mut stack = vec![root.to_path_buf()];
    while let Some(dir) = stack.pop() {
        let mut children: Vec<PathBuf> = fs::read_dir(&dir)
            .into_iter()
            .flatten()
            .flatten()
            .filter(|e| e.file_type().is_ok_and(|t| t.is_dir()))
            .map(|e| e.path())
            .collect();
        if let Some(hit) = children
            .iter()
            .map(|c| c.join("pack.json"))
            .find(|p| p.exists())
        {
            return Some(hit);
        }
        children.reverse();
        stack.extend(children);
    }
    None
}

pub(crate) fn copy_tree(src: &Path, dest: &Path) -> io::Result<()> {
    fs::create_dir_all(dest)?;
    for entry in fs::read_dir(src)? {
        let entry = entry?;
        let target = dest.join(entry.file_name());
        if entry.file_type()?.is_dir() {
            copy_tree(&entry.path(), &target)?;
        } else {
            fs::copy(entry.path(), target)?;
        }
    }
    Ok(())
}

/// `SoundPackInstaller._validate_extracted_pack`. Unlike
/// [`crate::pack::validate_sound_pack`] it only accepts plain file-name
/// entries: Python fails on `{"file": ..., "volume": ...}` entries here
/// (joining a path with a dict raises), so such packs cannot be installed
/// from the community browser.
fn validate_extracted_pack(pack_dir: &Path) -> Result<(), String> {
    let data = match read_json(&pack_dir.join("pack.json")) {
        Ok(Value::Object(data)) => data,
        Ok(_) => return Err("Missing 'name' field in pack.json".into()),
        Err(e) => return Err(format!("Invalid JSON in pack.json: {e}")),
    };
    if !data.contains_key("name") {
        return Err("Missing 'name' field in pack.json".into());
    }
    let sounds = match data.get("sounds") {
        None => return Err("Missing 'sounds' field in pack.json".into()),
        Some(Value::Object(sounds)) => sounds,
        Some(other) => {
            return Err(format!(
                "Error validating sound pack: '{}' object has no attribute 'items'",
                py_type_name(other)
            ))
        }
    };
    let mut missing = Vec::new();
    for entry in sounds.values() {
        let Value::String(file) = entry else {
            let path_type = if cfg!(windows) {
                "WindowsPath"
            } else {
                "PosixPath"
            };
            return Err(format!(
                "Error validating sound pack: unsupported operand type(s) for /: '{path_type}' and '{}'",
                py_type_name(entry)
            ));
        };
        if !pack_dir.join(file).exists() {
            missing.push(file.clone());
        }
    }
    if !missing.is_empty() {
        return Err(format!("Missing sound files: {}", missing.join(", ")));
    }
    Ok(())
}

/// `SoundPackInstaller.install_from_zip`: extract to a temporary folder,
/// find the first `pack.json`, validate, and copy that folder to
/// `<soundpacks_dir>/<pack_name or zip stem>`. Returns `(success, message)`.
pub fn install_from_zip(
    soundpacks_dir: &Path,
    zip_path: &Path,
    pack_name: Option<&str>,
) -> (bool, String) {
    let _ = fs::create_dir(soundpacks_dir);
    if !zip_path.exists() {
        return (false, format!("ZIP file not found: {}", zip_path.display()));
    }
    let pack_name = pack_name
        .filter(|n| !n.is_empty())
        .map(str::to_string)
        .unwrap_or_else(|| {
            zip_path
                .file_stem()
                .map(|s| s.to_string_lossy().into_owned())
                .unwrap_or_default()
        });
    match install_inner(soundpacks_dir, zip_path, &pack_name) {
        Ok(msg) => (true, msg),
        Err(msg) => (false, msg),
    }
}

fn install_inner(
    soundpacks_dir: &Path,
    zip_path: &Path,
    pack_name: &str,
) -> Result<String, String> {
    let failed = |e: &dyn std::fmt::Display| {
        tracing::error!("Error installing sound pack: {e}");
        format!("Installation failed: {e}")
    };
    let temp = tempfile::tempdir().map_err(|e| failed(&e))?;
    let file = fs::File::open(zip_path).map_err(|e| failed(&e))?;
    let mut archive = zip::ZipArchive::new(file).map_err(|_| "Invalid ZIP file".to_string())?;
    safe_extractall(&mut archive, temp.path()).map_err(|e| failed(&e))?;

    let pack_json = find_pack_json(temp.path()).ok_or("No pack.json file found in ZIP archive")?;
    let pack_dir = pack_json.parent().unwrap_or(temp.path());
    validate_extracted_pack(pack_dir).map_err(|e| format!("Invalid sound pack: {e}"))?;

    let target = soundpacks_dir.join(pack_name);
    if target.exists() {
        return Err(format!("Sound pack '{pack_name}' already exists"));
    }
    copy_tree(pack_dir, &target).map_err(|e| failed(&e))?;
    // Validation already parsed this pack.json, so it is an object with a name.
    let display = match read_json(&target.join("pack.json")) {
        Ok(Value::Object(data)) => data.get("name").map(py_str),
        _ => None,
    }
    .unwrap_or_else(|| pack_name.to_string());
    Ok(format!("Successfully installed sound pack '{display}'"))
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::Write;

    fn zip_with(entries: &[(&str, &str)]) -> zip::ZipArchive<io::Cursor<Vec<u8>>> {
        let mut buf = io::Cursor::new(Vec::new());
        {
            let mut w = zip::ZipWriter::new(&mut buf);
            for (name, body) in entries {
                w.start_file(*name, zip::write::SimpleFileOptions::default())
                    .unwrap();
                w.write_all(body.as_bytes()).unwrap();
            }
            w.finish().unwrap();
        }
        zip::ZipArchive::new(buf).unwrap()
    }

    #[test]
    fn zip_slip_is_rejected() {
        for bad in ["../escape.txt", "../../etc/passwd", "/tmp/evil.txt"] {
            let tmp = tempfile::tempdir().unwrap();
            let target = tmp.path().join("t");
            let err = safe_extractall(&mut zip_with(&[(bad, "pwned")]), &target).unwrap_err();
            assert!(err.contains("Zip Slip detected"), "{bad}: {err}");
            assert!(!tmp.path().join("escape.txt").exists());
        }
    }

    #[test]
    fn safe_entries_extract() {
        let tmp = tempfile::tempdir().unwrap();
        safe_extractall(
            &mut zip_with(&[("sounds/alert.wav", "data"), ("pack.json", "{}")]),
            tmp.path(),
        )
        .unwrap();
        assert!(tmp.path().join("sounds").join("alert.wav").exists());
        assert!(tmp.path().join("pack.json").exists());
    }
}
