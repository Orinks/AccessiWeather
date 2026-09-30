import AVFoundation
import Foundation
import UserNotifications

/// Plays short in-app cue sounds from the selected pack and copies the pack's alert clips into
/// `Library/Sounds` so `UNNotificationSound(named:)` can use them.
///
/// Uses the ambient category so cues mix with VoiceOver speech and any playing radio stream,
/// and respect the silent switch.
@MainActor
final class SoundManager: ObservableObject {
    let packs: [SoundPack]
    private let settings: SettingsStore
    private var players: [AVAudioPlayer] = []

    /// iOS refuses custom notification sounds longer than this.
    static let maxNotificationSoundSeconds: Double = 30

    init(settings: SettingsStore, packs: [SoundPack] = SoundPack.bundledPacks()) {
        self.settings = settings
        self.packs = packs
        if !packs.contains(where: { $0.id == settings.soundPackID }), let first = packs.first {
            settings.soundPackID = first.id
        }
        installNotificationSounds()
    }

    var selectedPack: SoundPack? {
        packs.first { $0.id == settings.soundPackID } ?? packs.first
    }

    func pack(withID id: String) -> SoundPack? {
        packs.first { $0.id == id }
    }

    /// Plays the cue for `event` unless sounds are off or the event is muted.
    func play(_ event: SoundEvent) {
        guard settings.soundEnabled, !settings.mutedSoundEvents.contains(event.rawValue) else { return }
        guard let url = selectedPack?.url(for: event) else { return }
        playClip(at: url)
    }

    /// Plays a pack's alert cue regardless of mute settings, for the preview button in Settings.
    func preview(_ pack: SoundPack) {
        guard let url = pack.url(for: .severe) ?? pack.url(for: .alertUpdated) else { return }
        playClip(at: url)
    }

    /// Plays a specific clip regardless of mute settings.
    func previewClip(at url: URL) {
        playClip(at: url)
    }

    private func playClip(at url: URL) {
        let session = AVAudioSession.sharedInstance()
        if session.category != .playback {
            try? session.setCategory(.ambient, mode: .default, options: [.mixWithOthers])
            try? session.setActive(true)
        }
        guard let player = try? AVAudioPlayer(contentsOf: url) else { return }
        players.removeAll { !$0.isPlaying }
        players.append(player)
        player.play()
    }

    // MARK: - Notification sounds

    /// Name passed to `UNNotificationSound(named:)` for an alert of `severity`, or nil to use the
    /// system default (sounds off, event muted, or clip missing/too long).
    func notificationSoundName(forSeverity severity: String) -> String? {
        let event = SoundEvent.forSeverity(severity)
        guard settings.soundEnabled, !settings.mutedSoundEvents.contains(event.rawValue),
              let pack = selectedPack, let source = pack.url(for: event) else { return nil }
        let name = Self.installedName(pack: pack, source: source)
        let installed = Self.librarySoundsDirectory().appendingPathComponent(name)
        return FileManager.default.fileExists(atPath: installed.path) ? name : nil
    }

    /// Copies every pack's alert clips into `Library/Sounds`, skipping clips over the 30 second limit.
    func installNotificationSounds() {
        let directory = Self.librarySoundsDirectory()
        try? FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        for pack in packs {
            for event in SoundEvent.alertEvents {
                guard let source = pack.url(for: event) else { continue }
                let destination = directory.appendingPathComponent(Self.installedName(pack: pack, source: source))
                if FileManager.default.fileExists(atPath: destination.path) { continue }
                guard let probe = try? AVAudioPlayer(contentsOf: source),
                      probe.duration <= Self.maxNotificationSoundSeconds else { continue }
                try? FileManager.default.copyItem(at: source, to: destination)
            }
        }
    }

    private static func installedName(pack: SoundPack, source: URL) -> String {
        "\(pack.id)-\(source.lastPathComponent)"
    }

    private static func librarySoundsDirectory() -> URL {
        FileManager.default.urls(for: .libraryDirectory, in: .userDomainMask)[0]
            .appendingPathComponent("Sounds", isDirectory: true)
    }
}
