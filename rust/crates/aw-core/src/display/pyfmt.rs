//! Python-compatible text helpers the presentation layer depends on.
//!
//! The Python presenter formats with f-strings, `str.title()`, `round()`,
//! `repr(float)` and `textwrap.fill`. These reproduce those exactly so the
//! Rust output matches character for character. (Rust's `{:.N}` already
//! rounds like Python's `:.Nf` - exact binary value, ties to even.)

use serde_json::Value;

/// `f"{x:.{prec}f}"`.
pub fn fixed(x: f64, prec: usize) -> String {
    format!("{x:.prec$}")
}

/// Python's `round(x)` (ties to even), as an integer.
pub fn round_int(x: f64) -> i64 {
    x.round_ties_even() as i64
}

/// `repr(x)` / `str(x)` / `f"{x}"` for a float.
pub fn repr_f64(x: f64) -> String {
    if x.is_nan() {
        return "nan".into();
    }
    if x.is_infinite() {
        return if x > 0.0 { "inf" } else { "-inf" }.into();
    }
    let abs = x.abs();
    if abs != 0.0 && !(1e-4..1e16).contains(&abs) {
        // Python switches to exponent notation outside [1e-4, 1e16) and
        // always writes a sign and at least two exponent digits.
        let s = format!("{x:e}");
        let (mantissa, exp) = s.split_once('e').unwrap_or((&s, "0"));
        let exp: i32 = exp.parse().unwrap_or(0);
        let sign = if exp < 0 { '-' } else { '+' };
        return format!("{mantissa}e{sign}{:02}", exp.abs());
    }
    let s = format!("{x}");
    if s.contains('.') {
        s
    } else {
        format!("{s}.0")
    }
}

fn is_cased(c: char) -> bool {
    c.is_lowercase() || c.is_uppercase()
}

/// `str.title()`: uppercase the first cased letter of every run, lowercase the rest.
pub fn title(s: &str) -> String {
    let mut out = String::with_capacity(s.len());
    let mut prev_cased = false;
    for c in s.chars() {
        if is_cased(c) {
            if prev_cased {
                out.extend(c.to_lowercase());
            } else {
                out.extend(c.to_uppercase());
            }
            prev_cased = true;
        } else {
            out.push(c);
            prev_cased = false;
        }
    }
    out
}

/// `str.capitalize()`: first character upper, the rest lower.
pub fn capitalize(s: &str) -> String {
    let mut chars = s.chars();
    match chars.next() {
        Some(first) => {
            let mut out: String = first.to_uppercase().collect();
            out.extend(chars.flat_map(char::to_lowercase));
            out
        }
        None => String::new(),
    }
}

/// `len(s)` (code points).
pub fn char_len(s: &str) -> usize {
    s.chars().count()
}

/// `text_formatters.truncate`: trim to `max_length` code points with "...".
pub fn truncate(text: &str, max_length: usize) -> String {
    if char_len(text) <= max_length {
        return text.to_string();
    }
    let kept: String = text.chars().take(max_length.saturating_sub(3)).collect();
    format!("{kept}...")
}

// ---------------------------------------------------------------------------
// textwrap.fill(text, width, break_long_words=False)
// ---------------------------------------------------------------------------

const WS: [char; 6] = ['\t', '\n', '\x0b', '\x0c', '\r', ' '];

fn is_ws(c: char) -> bool {
    WS.contains(&c)
}

fn is_word(c: char) -> bool {
    c.is_alphanumeric() || c == '_'
}

fn is_digit(c: char) -> bool {
    c.is_ascii_digit() || (!c.is_ascii() && c.is_numeric())
}

/// `[^\d\W]`
fn is_letter(c: char) -> bool {
    is_word(c) && !is_digit(c)
}

/// `[\w!"'&.,?]`
fn is_word_punct(c: char) -> bool {
    is_word(c) || matches!(c, '!' | '"' | '\'' | '&' | '.' | ',' | '?')
}

fn expand_tabs(text: &str) -> String {
    let mut out = String::with_capacity(text.len());
    let mut column = 0usize;
    for c in text.chars() {
        match c {
            '\t' => {
                let spaces = 8 - column % 8;
                out.extend(std::iter::repeat_n(' ', spaces));
                column += spaces;
            }
            '\n' | '\r' => {
                out.push(c);
                column = 0;
            }
            _ => {
                out.push(c);
                column += 1;
            }
        }
    }
    out
}

/// `TextWrapper._split` with `break_on_hyphens=True` (the `wordsep_re` regex).
fn split_chunks(c: &[char]) -> Vec<String> {
    let n = c.len();
    let at = |i: usize| c.get(i).copied();
    let dash_run_then_word = |start: usize| {
        let mut j = start;
        while j < n && c[j] == '-' {
            j += 1;
        }
        (j - start >= 2 && at(j).is_some_and(is_word)).then_some(j)
    };
    let mut chunks = Vec::new();
    let mut pos = 0;
    while pos < n {
        if is_ws(c[pos]) {
            let mut end = pos;
            while end < n && is_ws(c[end]) {
                end += 1;
            }
            chunks.push(c[pos..end].iter().collect());
            pos = end;
            continue;
        }
        // em-dash between words
        if pos > 0 && is_word_punct(c[pos - 1]) {
            if let Some(end) = dash_run_then_word(pos) {
                chunks.push(c[pos..end].iter().collect());
                pos = end;
                continue;
            }
        }
        // word, possibly hyphenated (lazy: shortest match wins)
        let mut end = pos + 1;
        let chunk_end = loop {
            // hyphenated word
            if at(end) == Some('-') {
                let behind_two = end >= 2 && is_letter(c[end - 2]) && is_letter(c[end - 1]);
                let behind_alt = end >= 3
                    && is_letter(c[end - 3])
                    && c[end - 2] == '-'
                    && is_letter(c[end - 1]);
                let ahead = at(end + 1).is_some_and(is_letter)
                    && (at(end + 2).is_some_and(is_letter)
                        || (at(end + 2) == Some('-') && at(end + 3).is_some_and(is_letter)));
                if (behind_two || behind_alt) && ahead {
                    break end + 1;
                }
            }
            // end of word
            if end == n || is_ws(c[end]) {
                break end;
            }
            // em-dash
            if is_word_punct(c[end - 1]) && dash_run_then_word(end).is_some() {
                break end;
            }
            end += 1;
        };
        chunks.push(c[pos..chunk_end].iter().collect());
        pos = chunk_end;
    }
    chunks
}

/// `textwrap.wrap(text, width, break_long_words=False)`.
pub fn wrap(text: &str, width: usize) -> Vec<String> {
    let munged: Vec<char> = expand_tabs(text)
        .chars()
        .map(|ch| if is_ws(ch) { ' ' } else { ch })
        .collect();
    let mut chunks = split_chunks(&munged);
    chunks.reverse();
    let is_blank = |s: &str| s.trim().is_empty();
    let mut lines: Vec<String> = Vec::new();
    while !chunks.is_empty() {
        let mut cur_line: Vec<String> = Vec::new();
        let mut cur_len = 0usize;
        if !lines.is_empty() && chunks.last().is_some_and(|s| is_blank(s)) {
            chunks.pop();
        }
        while let Some(last) = chunks.last() {
            let l = char_len(last);
            if cur_len + l <= width {
                cur_len += l;
                cur_line.push(chunks.pop().unwrap_or_default());
            } else {
                break;
            }
        }
        if chunks.last().is_some_and(|s| char_len(s) > width) && cur_line.is_empty() {
            cur_line.push(chunks.pop().unwrap_or_default());
        }
        if cur_line.last().is_some_and(|s| is_blank(s)) {
            cur_line.pop();
        }
        if !cur_line.is_empty() {
            lines.push(cur_line.concat());
        }
    }
    lines
}

/// `textwrap.fill(text, width=width, break_long_words=False)`.
pub fn wrap_text(text: &str, width: usize) -> String {
    wrap(text, width).join("\n")
}

// ---------------------------------------------------------------------------
// JSON values handled like Python objects (aviation advisories are raw dicts)
// ---------------------------------------------------------------------------

/// Python truthiness of a JSON value.
pub fn truthy(v: &Value) -> bool {
    match v {
        Value::Null => false,
        Value::Bool(b) => *b,
        Value::Number(n) => n.as_f64().is_some_and(|f| f != 0.0),
        Value::String(s) => !s.is_empty(),
        Value::Array(a) => !a.is_empty(),
        Value::Object(o) => !o.is_empty(),
    }
}

/// `str(value)` for a JSON value.
pub fn py_str(v: &Value) -> String {
    match v {
        Value::Null => "None".into(),
        Value::Bool(true) => "True".into(),
        Value::Bool(false) => "False".into(),
        Value::Number(n) => match (n.as_i64(), n.as_u64()) {
            (Some(i), _) => i.to_string(),
            (None, Some(u)) => u.to_string(),
            _ => repr_f64(n.as_f64().unwrap_or(0.0)),
        },
        Value::String(s) => s.clone(),
        Value::Array(items) => {
            let parts: Vec<String> = items.iter().map(py_repr).collect();
            format!("[{}]", parts.join(", "))
        }
        Value::Object(map) => {
            let parts: Vec<String> = map
                .iter()
                .map(|(k, v)| format!("{}: {}", py_repr(&Value::String(k.clone())), py_repr(v)))
                .collect();
            format!("{{{}}}", parts.join(", "))
        }
    }
}

fn py_repr(v: &Value) -> String {
    match v {
        Value::String(s) => {
            if s.contains('\'') && !s.contains('"') {
                format!("\"{s}\"")
            } else {
                format!("'{}'", s.replace('\\', "\\\\").replace('\'', "\\'"))
            }
        }
        other => py_str(other),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn repr_matches_python() {
        assert_eq!(repr_f64(5.0), "5.0");
        assert_eq!(repr_f64(3.25), "3.25");
        assert_eq!(repr_f64(-0.0), "-0.0");
        assert_eq!(repr_f64(1e16), "1e+16");
        assert_eq!(repr_f64(0.00001), "1e-05");
        assert_eq!(repr_f64(0.0001), "0.0001");
    }

    #[test]
    fn title_and_capitalize_match_python() {
        assert_eq!(title("pirate weather"), "Pirate Weather");
        assert_eq!(title("daily_trend"), "Daily_Trend");
        assert_eq!(title("2nd o'neil"), "2Nd O'Neil");
        assert_eq!(capitalize("due to WIND"), "Due to wind");
    }

    #[test]
    fn wrap_splits_hyphenated_words_like_textwrap() {
        let chunks = split_chunks(&"Hello there -- you goof-ball, use the -b option!".chars().collect::<Vec<_>>());
        assert_eq!(
            chunks,
            ["Hello", " ", "there", " ", "--", " ", "you", " ", "goof-", "ball,", " ", "use", " ", "the", " ", "-b", " ", "option!"]
        );
        assert_eq!(wrap_text("aaa bbb ccc", 7), "aaa bbb\nccc");
        assert_eq!(wrap_text("north-northwest wind", 10), "north-\nnorthwest\nwind");
        assert_eq!(wrap_text("averyveryverylongword x", 5), "averyveryverylongword\nx");
        assert_eq!(wrap_text("  ", 5), "");
    }
}
