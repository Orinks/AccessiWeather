//! `installer/create_icons.py`: the app icon (a sun behind a cloud on a blue
//! disc) as `.ico`, `.icns` and PNGs, plus the raw RGBA frames the tray
//! embeds. Everything lands in `crates/aw-app/ui/`, where packaging, the
//! Windows executable resource and the tray pick it up.

use std::f64::consts::{PI, TAU};
use std::fs::File;
use std::io::BufWriter;
use std::path::PathBuf;

use image::codecs::ico::{IcoEncoder, IcoFrame};
use image::{ExtendedColorType, ImageFormat, Rgba, RgbaImage};

use crate::Result;

const WINDOWS_SIZES: [u32; 7] = [16, 24, 32, 48, 64, 128, 256];
const MACOS_SIZES: [u32; 7] = [16, 32, 64, 128, 256, 512, 1024];
const PNG_SIZES: [u32; 5] = [16, 32, 64, 128, 256];
/// The `.ico` frames the tray loads (`ui/system_tray.py` reads app.ico).
const TRAY_SIZES: [u32; 4] = [16, 24, 32, 48];

const SKY_BLUE: [u8; 3] = [70, 130, 180];
const SUN_YELLOW: [u8; 3] = [255, 200, 50];
const SUN_ORANGE: [u8; 3] = [255, 165, 0];
const CLOUD_WHITE: [u8; 3] = [245, 245, 250];
const CLOUD_SHADOW: [u8; 3] = [200, 200, 210];

pub fn icon_dir() -> PathBuf {
    crate::rust_dir().join("crates").join("aw-app").join("ui")
}

pub fn generate() -> Result<()> {
    let dir = icon_dir();
    std::fs::create_dir_all(&dir)?;

    let mut frames = Vec::new();
    for size in WINDOWS_SIZES.into_iter().rev() {
        let mut png = Vec::new();
        weather_icon(size).write_to(&mut std::io::Cursor::new(&mut png), ImageFormat::Png)?;
        frames.push(IcoFrame::with_encoded(
            png,
            size,
            size,
            ExtendedColorType::Rgba8,
        )?);
    }
    IcoEncoder::new(BufWriter::new(File::create(dir.join("app.ico"))?)).encode_images(&frames)?;
    eprintln!("Created: {}", dir.join("app.ico").display());

    let mut family = icns::IconFamily::new();
    for size in MACOS_SIZES {
        let image = icns::Image::from_data(
            icns::PixelFormat::RGBA,
            size,
            size,
            weather_icon(size).into_raw(),
        )?;
        family.add_icon(&image)?;
    }
    family.write(BufWriter::new(File::create(dir.join("app.icns"))?))?;
    eprintln!("Created: {}", dir.join("app.icns").display());

    weather_icon(1024).save(dir.join("app_icon_master.png"))?;
    for size in PNG_SIZES {
        weather_icon(size).save(dir.join(format!("app_{size}.png")))?;
    }
    for size in TRAY_SIZES {
        std::fs::write(
            dir.join(format!("tray_{size}.rgba")),
            weather_icon(size).into_raw(),
        )?;
    }
    eprintln!("All icons generated in {}", dir.display());
    Ok(())
}

/// The icon at `size` px, drawn the way Pillow's ImageDraw draws it: no
/// anti-aliasing, shape coordinates truncated to whole pixels.
pub fn weather_icon(size: u32) -> RgbaImage {
    let s = f64::from(size);
    let mut img = RgbaImage::new(size, size);
    let (cx, cy, sun_r) = (s * 0.4, s * 0.4, s * 0.25);

    let margin = s * 0.02;
    ellipse(&mut img, [margin, margin, s - margin, s - margin], SKY_BLUE);

    let ray_length = sun_r * 0.6;
    let ray_width = (s * 0.04).max(2.0).trunc() as i64;
    for i in 0..8 {
        let angle = TAU * f64::from(i) / 8.0 - PI / 8.0;
        let (sin, cos) = angle.sin_cos();
        let (inner, outer) = (sun_r + s * 0.02, sun_r + ray_length);
        wide_line(
            &mut img,
            [
                cx + inner * cos,
                cy + inner * sin,
                cx + outer * cos,
                cy + outer * sin,
            ],
            ray_width,
            SUN_ORANGE,
        );
    }
    ellipse(
        &mut img,
        [cx - sun_r, cy - sun_r, cx + sun_r, cy + sun_r],
        SUN_YELLOW,
    );

    let (x, y, w, h) = (s * 0.55, s * 0.6, s * 0.45, s * 0.25);
    let shadow = s * 0.02;
    cloud(&mut img, x + shadow, y + shadow, w, h, CLOUD_SHADOW);
    cloud(&mut img, x, y, w, h, CLOUD_WHITE);
    img
}

/// Overlapping circles: left, top middle, right, bottom left, bottom right.
fn cloud(img: &mut RgbaImage, x: f64, y: f64, w: f64, h: f64, color: [u8; 3]) {
    for (cx, cy, r) in [
        (x - w * 0.25, y, h * 0.45),
        (x, y - h * 0.15, h * 0.55),
        (x + w * 0.2, y, h * 0.45),
        (x - w * 0.1, y + h * 0.1, h * 0.4),
        (x + w * 0.1, y + h * 0.1, h * 0.4),
    ] {
        ellipse(img, [cx - r, cy - r, cx + r, cy + r], color);
    }
}

fn put(img: &mut RgbaImage, x: i64, y: i64, [r, g, b]: [u8; 3]) {
    if (0..i64::from(img.width())).contains(&x) && (0..i64::from(img.height())).contains(&y) {
        img.put_pixel(x as u32, y as u32, Rgba([r, g, b, 255]));
    }
}

/// Pillow's `ellipseNew` with `fill`: horizontal spans of the ellipse in the
/// truncated box, traced on a doubled grid (`quarter_*` / `ellipse_*` in
/// Pillow's draw.c).
fn ellipse(img: &mut RgbaImage, bbox: [f64; 4], color: [u8; 3]) {
    let [x0, y0, x1, y1] = bbox.map(|v| v.trunc() as i64);
    let (a, b) = (x1 - x0, y1 - y0);
    if a < 0 || b < 0 {
        return;
    }
    for (l, y, r) in ellipse_spans(a, b, a + b) {
        let py = y0 + (y + b) / 2;
        for px in x0 + (l + a) / 2..=x0 + (r + a) / 2 {
            put(img, px, py, color);
        }
    }
}

/// One quarter of an ellipse with semi-axes `a`, `b` on the doubled grid.
struct Quarter {
    a2: i64,
    b2: i64,
    cx: i64,
    cy: i64,
    ex: i64,
    ey: i64,
    finished: bool,
}

impl Quarter {
    fn new(a: i64, b: i64) -> Self {
        Quarter {
            a2: a * a,
            b2: b * b,
            cx: a,
            cy: b % 2,
            ex: a % 2,
            ey: b,
            finished: a < 0 || b < 0,
        }
    }

    fn delta(&self, x: i64, y: i64) -> i64 {
        (self.a2 * y * y + self.b2 * x * x - self.a2 * self.b2).abs()
    }

    fn next(&mut self) -> Option<(i64, i64)> {
        if self.finished {
            return None;
        }
        let point = (self.cx, self.cy);
        if self.cx == self.ex && self.cy == self.ey {
            self.finished = true;
        } else {
            let (mut nx, mut ny) = (self.cx, self.cy + 2);
            let mut ndelta = self.delta(nx, ny);
            if nx > 1 {
                let d = self.delta(self.cx - 2, self.cy + 2);
                if ndelta > d {
                    (nx, ny, ndelta) = (self.cx - 2, self.cy + 2, d);
                }
                if ndelta > self.delta(self.cx - 2, self.cy) {
                    (nx, ny) = (self.cx - 2, self.cy);
                }
            }
            (self.cx, self.cy) = (nx, ny);
        }
        Some(point)
    }
}

/// `(x0, y, x1)` spans on the doubled grid for an ellipse `w` thick.
fn ellipse_spans(a: i64, b: i64, w: i64) -> Vec<(i64, i64, i64)> {
    let leftmost = a % 2;
    let mut outer = Quarter::new(a, b);
    let Some((mut pr, mut py)) = outer.next().filter(|_| w >= 1) else {
        return Vec::new();
    };
    let mut inner = Quarter::new(a - 2 * (w - 1), b - 2 * (w - 1));
    let mut pl = leftmost;
    let mut spans = Vec::new();
    loop {
        let (y, mut l, r) = (py, pl, pr);
        let mut finished = true;
        while let Some((cx, cy)) = outer.next() {
            if cy > y {
                (pr, py, finished) = (cx, cy, false);
                break;
            }
        }
        pl = leftmost;
        while let Some((cx, cy)) = inner.next() {
            if cy > y {
                pl = cx;
                break;
            }
            l = cx;
        }
        let mut quad = Vec::new();
        if (l > 0 || l < r) && y > 0 {
            quad.push((if l == 0 { 2 } else { l }, y, r));
        }
        if y > 0 {
            quad.push((-r, y, -l));
        }
        if l > 0 || l < r {
            quad.push((if l == 0 { 2 } else { l }, -y, r));
        }
        quad.push((-r, -y, -l));
        spans.extend(quad);
        if finished {
            return spans;
        }
    }
}

/// Pillow's `ROUND_UP`: round half away from zero.
fn round_up(f: f64) -> i64 {
    (f.abs() + 0.5).floor().copysign(f) as i64
}

/// Pillow's `ROUND_DOWN`: round half toward zero.
fn round_down(f: f64) -> i64 {
    (f.abs() - 0.5).ceil().copysign(f) as i64
}

/// Pillow's `ImagingDrawWideLine`: the quadrilateral around the truncated
/// segment, half as wide as `width - 1` on each side.
fn wide_line(img: &mut RgbaImage, xy: [f64; 4], width: i64, color: [u8; 3]) {
    let [x0, y0, x1, y1] = xy.map(|v| v.trunc() as i64);
    let (dx, dy) = (x1 - x0, y1 - y0);
    if dx == 0 && dy == 0 {
        put(img, x0, y0, color);
        return;
    }
    let hypot = (dx as f64).hypot(dy as f64);
    let half = (width - 1) as f64 / 2.0;
    let ratio_max = round_up(half) as f64 / hypot;
    let ratio_min = round_down(half) as f64 / hypot;
    let (dxmin, dxmax) = (
        round_down(ratio_min * dy as f64),
        round_down(ratio_max * dy as f64),
    );
    let (dymin, dymax) = (
        round_down(ratio_min * dx as f64),
        round_down(ratio_max * dx as f64),
    );
    let quad = [
        (x0 - dxmin, y0 + dymax),
        (x1 - dxmin, y1 + dymax),
        (x1 + dxmax, y1 - dymin),
        (x0 + dxmax, y0 - dymin),
    ];
    // Pillow's polygon filler: per scanline, from the leftmost edge
    // crossing (rounded half up) to the rightmost (rounded half down).
    let edges = (0..4).map(|i| (quad[i], quad[(i + 1) % 4]));
    let (ymin, ymax) = (
        quad.iter().map(|p| p.1).min().unwrap(),
        quad.iter().map(|p| p.1).max().unwrap(),
    );
    for y in ymin..=ymax {
        let crossings: Vec<f64> = edges
            .clone()
            .filter(|((_, ay), (_, by))| (*ay.min(by)..=*ay.max(by)).contains(&y))
            .flat_map(|((ax, ay), (bx, by))| {
                if ay == by {
                    vec![ax as f64, bx as f64]
                } else {
                    vec![ax as f64 + (y - ay) as f64 * (bx - ax) as f64 / (by - ay) as f64]
                }
            })
            .collect();
        let left = crossings.iter().copied().fold(f64::INFINITY, f64::min);
        let right = crossings.iter().copied().fold(f64::NEG_INFINITY, f64::max);
        for x in round_up(left)..=round_down(right) {
            put(img, x, y, color);
        }
    }
}

#[cfg(test)]
mod tests {
    //! The drawing against Pillow's, from `rust/tools/golden/icons.py`.

    use super::*;

    #[test]
    fn matches_pillow_rendering() {
        let dir = std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("../testdata/golden/icons");
        for size in [16u32, 32, 64, 256] {
            let pillow = image::open(dir.join(format!("app_{size}.png")))
                .unwrap()
                .into_rgba8();
            assert!(
                weather_icon(size) == pillow,
                "{size}px icon differs from Pillow's"
            );
        }
    }
}
