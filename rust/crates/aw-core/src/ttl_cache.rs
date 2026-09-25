//! In-memory cache with per-entry time-to-live. Port of `Cache` in
//! `accessiweather/cache.py` (used for API responses and AI explanations).

use std::collections::HashMap;
use std::time::{Duration, Instant};

#[derive(Debug, Clone)]
pub struct TtlCache<V> {
    data: HashMap<String, (V, Instant)>,
    pub default_ttl: Duration,
}

impl<V: Clone> TtlCache<V> {
    /// Python's default TTL is 300 seconds.
    pub fn new(default_ttl: Duration) -> Self {
        Self {
            data: HashMap::new(),
            default_ttl,
        }
    }

    /// The cached value, dropping it first if it has expired.
    pub fn get(&mut self, key: &str) -> Option<V> {
        let now = Instant::now();
        match self.data.get(key) {
            Some((_, expires)) if *expires < now => {
                self.data.remove(key);
                None
            }
            Some((value, _)) => Some(value.clone()),
            None => None,
        }
    }

    /// Store `value` for `ttl` (the default TTL when `None`).
    pub fn set(&mut self, key: impl Into<String>, value: V, ttl: Option<Duration>) {
        let expires = Instant::now() + ttl.unwrap_or(self.default_ttl);
        self.data.insert(key.into(), (value, expires));
    }

    pub fn has_key(&mut self, key: &str) -> bool {
        self.get(key).is_some()
    }

    pub fn invalidate(&mut self, key: &str) {
        self.data.remove(key);
    }

    pub fn clear(&mut self) {
        self.data.clear();
    }

    /// Remove every expired entry.
    pub fn cleanup(&mut self) {
        let now = Instant::now();
        self.data.retain(|_, (_, expires)| *expires >= now);
    }
}

impl<V: Clone> Default for TtlCache<V> {
    fn default() -> Self {
        Self::new(Duration::from_secs(300))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    const SHORT: Duration = Duration::from_millis(10);

    fn wait() {
        std::thread::sleep(Duration::from_millis(20));
    }

    #[test]
    fn set_get_and_missing() {
        let mut cache = TtlCache::new(Duration::from_secs(60));
        cache.set("key1", "value1", None);
        assert_eq!(cache.get("key1"), Some("value1"));
        assert_eq!(cache.get("nonexistent"), None);
        assert!(cache.has_key("key1"));
        assert!(!cache.has_key("missing"));
    }

    #[test]
    fn entries_expire_with_default_or_custom_ttl() {
        let mut cache = TtlCache::new(SHORT);
        cache.set("default", 1, None);
        let mut custom = TtlCache::new(Duration::from_secs(60));
        custom.set("custom", 2, Some(SHORT));
        wait();
        assert_eq!(cache.get("default"), None);
        assert_eq!(custom.get("custom"), None);
    }

    #[test]
    fn invalidate_clear_and_cleanup() {
        let mut cache = TtlCache::new(SHORT);
        cache.set("a", 1, None);
        cache.set("b", 2, Some(Duration::from_secs(60)));
        cache.invalidate("missing");
        wait();
        cache.cleanup();
        assert_eq!(cache.get("a"), None);
        assert_eq!(cache.get("b"), Some(2));
        cache.clear();
        assert_eq!(cache.get("b"), None);
    }
}
