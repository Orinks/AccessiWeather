import Foundation

enum ICAOCodeValidation {
    static func normalized(_ code: String) -> String {
        code.trimmingCharacters(in: .whitespacesAndNewlines).uppercased()
    }

    static func error(for code: String) -> String? {
        let normalizedCode = normalized(code)
        if normalizedCode.isEmpty {
            return "Please enter a four-letter ICAO airport code."
        }
        guard normalizedCode.range(of: "^[A-Z]{4}$", options: .regularExpression) != nil else {
            return "Airport codes must be exactly four letters (e.g., KJFK)."
        }
        return nil
    }
}

enum AviationValue: Equatable, Decodable {
    case number(Double)
    case text(String)

    var number: Double? {
        guard case .number(let value) = self else { return nil }
        return value
    }

    var text: String? {
        guard case .text(let value) = self else { return nil }
        return value
    }

    var displayValue: String {
        switch self {
        case .number(let value):
            return AviationWeatherFormatting.number(value)
        case .text(let value):
            return value
        }
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()
        if let number = try? container.decode(Double.self) {
            self = .number(number)
        } else if let text = try? container.decode(String.self) {
            self = .text(text)
        } else {
            throw DecodingError.typeMismatch(
                AviationValue.self,
                DecodingError.Context(codingPath: decoder.codingPath, debugDescription: "Expected a number or string.")
            )
        }
    }
}

struct AviationCloud: Decodable, Equatable {
    var cover: String?
    var base: AviationValue?
}

struct METARObservation: Decodable, Equatable {
    var rawOb: String?
    var obsTime: AviationValue?
    var wdir: AviationValue?
    var wspd: AviationValue?
    var wgst: AviationValue?
    var visib: AviationValue?
    var clouds: [AviationCloud]?
    var temperature: AviationValue?
    var dewpoint: AviationValue?
    var altim: AviationValue?
    var wxString: String?

    enum CodingKeys: String, CodingKey {
        case rawOb
        case obsTime
        case wdir
        case wspd
        case wgst
        case visib
        case clouds
        case temperature = "temp"
        case dewpoint = "dewp"
        case altim
        case wxString
    }

    var observationDate: Date? {
        AviationWeatherFormatting.date(from: obsTime)
    }
}

struct TAFForecast: Decodable, Equatable {
    var timeFrom: AviationValue?
    var timeTo: AviationValue?
    var wdir: AviationValue?
    var wspd: AviationValue?
    var wgst: AviationValue?
    var visib: AviationValue?
    var clouds: [AviationCloud]?
    var wxString: String?
    var fcstChange: String?

    var startDate: Date? { AviationWeatherFormatting.date(from: timeFrom) }
    var endDate: Date? { AviationWeatherFormatting.date(from: timeTo) }
}

struct TAFProduct: Decodable, Equatable {
    var rawTAF: String?
    var fcsts: [TAFForecast]?
}

struct AviationWeather: Equatable {
    var metars: [METARObservation]
    var tafs: [TAFProduct]
}

enum AviationWeatherFormatting {
    static func number(_ value: Double) -> String {
        if value.rounded() == value {
            return String(Int(value))
        }
        return String(format: "%.1f", value)
    }

    static func date(from value: AviationValue?) -> Date? {
        guard let value else { return nil }
        switch value {
        case .number(let timestamp):
            return Date(timeIntervalSince1970: timestamp > 1_000_000_000_000 ? timestamp / 1000 : timestamp)
        case .text(let text):
            if let timestamp = Double(text) {
                return Date(timeIntervalSince1970: timestamp > 1_000_000_000_000 ? timestamp / 1000 : timestamp)
            }
            let formatter = ISO8601DateFormatter()
            return formatter.date(from: text)
        }
    }

    static func wind(direction: AviationValue?, speed: AviationValue?, gust: AviationValue?) -> String? {
        let directionText: String?
        if direction?.text?.uppercased() == "VRB" {
            directionText = "variable direction"
        } else if let degrees = direction?.number {
            directionText = "\(number(degrees)) degrees"
        } else {
            directionText = nil
        }
        var parts: [String] = []
        if let directionText {
            parts.append("from \(directionText)")
        }
        if let speed {
            parts.append("at \(speed.displayValue) knots")
        }
        if let gust {
            parts.append("gusting \(gust.displayValue)")
        }
        return parts.isEmpty ? nil : parts.joined(separator: ", ")
    }

    static func visibility(_ value: AviationValue?) -> String? {
        value.map { "\($0.displayValue) statute miles" }
    }

    static func clouds(_ clouds: [AviationCloud]?) -> String? {
        guard let clouds, !clouds.isEmpty else { return nil }
        let descriptions = clouds.map { cloud -> String in
            let cover = cloud.cover.map(cloudCoverName) ?? "Cloud layer"
            guard let base = cloud.base?.number else { return cover }
            return "\(cover) at \(groupedInteger(base)) feet"
        }
        return descriptions.joined(separator: ", ")
    }

    static func altimeterHectopascals(_ value: AviationValue?) -> Double? {
        guard let value = value?.number else { return nil }
        return value < 100 ? value * 33.8639 : value
    }

    private static func cloudCoverName(_ code: String) -> String {
        switch code.uppercased() {
        case "FEW": return "Few"
        case "SCT": return "Scattered"
        case "BKN": return "Broken"
        case "OVC": return "Overcast"
        case "VV": return "Vertical visibility"
        case "SKC", "CLR": return "Clear"
        case "NSC", "NCD": return "No significant clouds"
        default: return code
        }
    }

    private static func groupedInteger(_ value: Double) -> String {
        let formatter = NumberFormatter()
        formatter.locale = Locale(identifier: "en_US")
        formatter.numberStyle = .decimal
        formatter.maximumFractionDigits = 0
        return formatter.string(from: NSNumber(value: value)) ?? number(value)
    }
}
