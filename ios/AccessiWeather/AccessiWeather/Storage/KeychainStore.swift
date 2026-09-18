import Foundation
import Security

/// Stores provider API keys in the iOS Keychain as generic passwords.
enum KeychainStore {
    enum Key: String, CaseIterable {
        case pirateWeather = "pirate_weather_api_key"
        case airNow = "airnow_api_key"
        case avwx = "avwx_api_key"
        case openRouter = "openrouter_api_key"

        var title: String {
            switch self {
            case .pirateWeather: return "Pirate Weather API key"
            case .airNow: return "AirNow API key"
            case .avwx: return "AVWX API key"
            case .openRouter: return "OpenRouter API key"
            }
        }
    }

    private static let service = "net.orinks.AccessiWeather"

    private static func query(for key: Key) -> [String: Any] {
        [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: key.rawValue,
        ]
    }

    static func read(_ key: Key) -> String {
        var query = query(for: key)
        query[kSecReturnData as String] = true
        query[kSecMatchLimit as String] = kSecMatchLimitOne
        var item: CFTypeRef?
        let status = SecItemCopyMatching(query as CFDictionary, &item)
        guard status == errSecSuccess, let data = item as? Data else { return "" }
        return String(decoding: data, as: UTF8.self)
    }

    static func write(_ value: String, for key: Key) {
        let trimmed = value.trimmingCharacters(in: .whitespacesAndNewlines)
        if trimmed.isEmpty {
            SecItemDelete(query(for: key) as CFDictionary)
            return
        }
        let data = Data(trimmed.utf8)
        let attributes: [String: Any] = [
            kSecValueData as String: data,
            kSecAttrAccessible as String: kSecAttrAccessibleAfterFirstUnlock,
        ]
        let status = SecItemUpdate(query(for: key) as CFDictionary, attributes as CFDictionary)
        if status == errSecItemNotFound {
            var addQuery = query(for: key)
            addQuery.merge(attributes) { _, new in new }
            SecItemAdd(addQuery as CFDictionary, nil)
        }
    }
}
