//! PEP 440 version ordering, as `packaging.version.Version` compares the
//! release tags in `services/simple_update.py`.

use std::sync::LazyLock;

use regex::Regex;

/// `packaging.version.VERSION_PATTERN`, anchored the way `Version` uses it.
static VERSION: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(
        r"(?xi)^\s*
        v?
        (?:
            (?:(?P<epoch>[0-9]+)!)?
            (?P<release>[0-9]+(?:\.[0-9]+)*)
            (?P<pre>
                [-_\.]?
                (?P<pre_l>alpha|a|beta|b|preview|pre|c|rc)
                [-_\.]?
                (?P<pre_n>[0-9]+)?
            )?
            (?P<post>
                (?:-(?P<post_n1>[0-9]+))
                |
                (?:
                    [-_\.]?
                    (?P<post_l>post|rev|r)
                    [-_\.]?
                    (?P<post_n2>[0-9]+)?
                )
            )?
            (?P<dev>
                [-_\.]?
                (?P<dev_l>dev)
                [-_\.]?
                (?P<dev_n>[0-9]+)?
            )?
        )
        (?:\+(?P<local>[a-z0-9]+(?:[-_\.][a-z0-9]+)*))?
        \s*$",
    )
    .expect("valid PEP 440 pattern")
});

#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord)]
enum Pre {
    NegInf,
    Tag(u8, u64),
    PosInf,
}

#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord)]
enum LocalPart {
    Text(String),
    Number(u64),
}

/// A parsed version; ordering follows `packaging`'s `_cmpkey`.
#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord)]
pub struct Version {
    epoch: u64,
    release: Vec<u64>,
    pre: Pre,
    post: Option<u64>,
    /// `(0, n)` for a dev release, `(1, 0)` (= +infinity) otherwise.
    dev: (u8, u64),
    local: Option<Vec<LocalPart>>,
}

impl Version {
    /// `Version(text)`; `None` where Python raises `InvalidVersion`.
    pub fn parse(text: &str) -> Option<Self> {
        let caps = VERSION.captures(text)?;
        let num = |name: &str| -> Option<Option<u64>> {
            match caps.name(name) {
                Some(m) => m.as_str().parse().ok().map(Some),
                None => Some(None),
            }
        };
        let epoch = num("epoch")?.unwrap_or(0);
        let mut release = caps["release"]
            .split('.')
            .map(|p| p.parse().ok())
            .collect::<Option<Vec<u64>>>()?;
        while release.last() == Some(&0) {
            release.pop();
        }
        let pre = match caps.name("pre_l") {
            Some(l) => {
                let rank = match l.as_str().to_lowercase().as_str() {
                    "alpha" | "a" => 0,
                    "beta" | "b" => 1,
                    _ => 2,
                };
                Some((rank, num("pre_n")?.unwrap_or(0)))
            }
            None => None,
        };
        let post = if caps.name("post").is_some() {
            Some(num("post_n1")?.or(num("post_n2")?).unwrap_or(0))
        } else {
            None
        };
        let dev = if caps.name("dev").is_some() {
            Some(num("dev_n")?.unwrap_or(0))
        } else {
            None
        };
        let local = caps.name("local").map(|m| {
            m.as_str()
                .split(['-', '_', '.'])
                .map(|p| match p.parse() {
                    Ok(n) => LocalPart::Number(n),
                    Err(_) => LocalPart::Text(p.to_lowercase()),
                })
                .collect()
        });
        Some(Self {
            epoch,
            release,
            pre: match pre {
                Some((rank, n)) => Pre::Tag(rank, n),
                None if post.is_none() && dev.is_some() => Pre::NegInf,
                None => Pre::PosInf,
            },
            post,
            dev: dev.map_or((1, 0), |n| (0, n)),
            local,
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn v(s: &str) -> Version {
        Version::parse(s).unwrap_or_else(|| panic!("{s} should parse"))
    }

    #[test]
    fn ordering_follows_packaging() {
        let ordered = [
            "1.0.dev1",
            "1.0a1",
            "1.0a2.dev1",
            "1.0b1",
            "1.0rc1",
            "1.0",
            "1.0+abc",
            "1.0+5",
            "1.0.post1.dev1",
            "1.0.post1",
            "1.1",
            "2!0.1",
        ];
        for pair in ordered.windows(2) {
            assert!(v(pair[0]) < v(pair[1]), "{} < {}", pair[0], pair[1]);
        }
        assert_eq!(v("1.0"), v("1.0.0"));
        assert_eq!(v("V1.0-1"), v("1.0.post1"));
        assert_eq!(v(" 0.10.1 "), v("0.10.1"));
    }

    #[test]
    fn invalid_versions_are_rejected() {
        for bad in ["", "abc", "0.11.0-rust.1", "1.0+", "20260131x", "1..0"] {
            assert!(Version::parse(bad).is_none(), "{bad}");
        }
    }
}
