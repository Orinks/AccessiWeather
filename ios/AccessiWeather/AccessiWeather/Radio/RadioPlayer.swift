import AVFoundation
import Combine
import MediaPlayer
import SwiftUI

/// Streams a NOAA Weather Radio station with AVPlayer, keeps playing in the background,
/// publishes lock-screen metadata, and announces state changes to VoiceOver.
@MainActor
final class RadioPlayer: ObservableObject {
    enum Status: Equatable {
        case idle
        case connecting
        case playing
        case interrupted
        case failed(String)

        var text: String {
            switch self {
            case .idle: return "Stopped"
            case .connecting: return "Connecting…"
            case .playing: return "Playing"
            case .interrupted: return "Paused by another app"
            case .failed(let message): return "Stream unavailable: \(message)"
            }
        }
    }

    @Published private(set) var station: RadioStation?
    @Published private(set) var status: Status = .idle

    private var player: AVPlayer?
    private var candidates: [URL] = []
    private var statusObservation: NSKeyValueObservation?
    private var observers: [NSObjectProtocol] = []
    private var remoteCommandsConfigured = false

    var isPlaying: Bool {
        status == .playing || status == .connecting
    }

    init() {
        let center = NotificationCenter.default
        observers.append(center.addObserver(forName: AVAudioSession.interruptionNotification, object: nil, queue: .main) { [weak self] note in
            MainActor.assumeIsolated { self?.handleInterruption(note) }
        })
        observers.append(center.addObserver(forName: AVAudioSession.routeChangeNotification, object: nil, queue: .main) { [weak self] note in
            MainActor.assumeIsolated { self?.handleRouteChange(note) }
        })
    }

    func play(_ station: RadioStation) {
        stopPlayer()
        self.station = station
        candidates = station.candidateURLs
        status = .connecting
        configureRemoteCommands()
        do {
            let session = AVAudioSession.sharedInstance()
            try session.setCategory(.playback, mode: .spokenAudio, options: [])
            try session.setActive(true)
        } catch {
            fail("Could not start audio. \(error.localizedDescription)")
            return
        }
        tryNextCandidate()
        announce("Connecting to \(station.name), \(station.callSign)")
    }

    func stop(announceStop: Bool = true) {
        let name = station?.name
        stopPlayer()
        status = .idle
        MPNowPlayingInfoCenter.default().nowPlayingInfo = nil
        try? AVAudioSession.sharedInstance().setActive(false, options: .notifyOthersOnDeactivation)
        if announceStop, let name {
            announce("Stopped \(name)")
        }
    }

    func toggle(_ station: RadioStation) {
        if self.station == station && isPlaying {
            stop()
        } else {
            play(station)
        }
    }

    // MARK: - Playback

    private func tryNextCandidate() {
        guard let station else { return }
        guard !candidates.isEmpty else {
            fail("No working stream found for \(station.callSign)")
            return
        }
        let url = candidates.removeFirst()
        let item = AVPlayerItem(url: url)
        let player = AVPlayer(playerItem: item)
        player.automaticallyWaitsToMinimizeStalling = true
        self.player = player

        statusObservation = item.observe(\.status, options: [.new]) { [weak self] item, _ in
            Task { @MainActor in
                guard let self, self.player?.currentItem === item else { return }
                switch item.status {
                case .readyToPlay:
                    self.status = .playing
                    self.updateNowPlaying()
                    self.announce("Playing \(station.name)")
                case .failed:
                    self.tryNextCandidate()
                default:
                    break
                }
            }
        }
        observers.append(NotificationCenter.default.addObserver(forName: .AVPlayerItemFailedToPlayToEndTime, object: item, queue: .main) { [weak self] _ in
            MainActor.assumeIsolated { self?.tryNextCandidate() }
        })
        observers.append(NotificationCenter.default.addObserver(forName: .AVPlayerItemPlaybackStalled, object: item, queue: .main) { [weak self] _ in
            MainActor.assumeIsolated {
                guard let self, self.status == .playing else { return }
                self.status = .connecting
                self.player?.play()
            }
        })
        player.play()
        updateNowPlaying()
    }

    private func stopPlayer() {
        player?.pause()
        player = nil
        statusObservation = nil
        for observer in observers.dropFirst(2) {
            NotificationCenter.default.removeObserver(observer)
        }
        observers = Array(observers.prefix(2))
    }

    private func fail(_ message: String) {
        stopPlayer()
        status = .failed(message)
        announce(message)
    }

    // MARK: - Interruptions and routes

    private func handleInterruption(_ note: Notification) {
        guard let raw = note.userInfo?[AVAudioSessionInterruptionTypeKey] as? UInt,
              let type = AVAudioSession.InterruptionType(rawValue: raw) else { return }
        switch type {
        case .began:
            guard isPlaying else { return }
            player?.pause()
            status = .interrupted
        case .ended:
            guard status == .interrupted else { return }
            let optionsRaw = note.userInfo?[AVAudioSessionInterruptionOptionKey] as? UInt ?? 0
            if AVAudioSession.InterruptionOptions(rawValue: optionsRaw).contains(.shouldResume) {
                try? AVAudioSession.sharedInstance().setActive(true)
                player?.play()
                status = .playing
                announce("Resumed \(station?.name ?? "radio")")
            } else {
                stop(announceStop: false)
            }
        @unknown default:
            break
        }
    }

    private func handleRouteChange(_ note: Notification) {
        guard let raw = note.userInfo?[AVAudioSessionRouteChangeReasonKey] as? UInt,
              let reason = AVAudioSession.RouteChangeReason(rawValue: raw) else { return }
        if reason == .oldDeviceUnavailable, isPlaying {
            // Headphones unplugged: pause rather than blast the speaker.
            stop()
        }
    }

    // MARK: - Lock screen

    private func configureRemoteCommands() {
        guard !remoteCommandsConfigured else { return }
        remoteCommandsConfigured = true
        let center = MPRemoteCommandCenter.shared()
        center.playCommand.addTarget { [weak self] _ in
            Task { @MainActor in
                guard let self, let station = self.station else { return }
                if !self.isPlaying { self.play(station) }
            }
            return .success
        }
        center.pauseCommand.addTarget { [weak self] _ in
            Task { @MainActor in self?.stop() }
            return .success
        }
        center.stopCommand.addTarget { [weak self] _ in
            Task { @MainActor in self?.stop() }
            return .success
        }
        center.togglePlayPauseCommand.addTarget { [weak self] _ in
            Task { @MainActor in
                guard let self, let station = self.station else { return }
                self.toggle(station)
            }
            return .success
        }
        center.nextTrackCommand.isEnabled = false
        center.previousTrackCommand.isEnabled = false
    }

    private func updateNowPlaying() {
        guard let station else { return }
        MPNowPlayingInfoCenter.default().nowPlayingInfo = [
            MPMediaItemPropertyTitle: "\(station.name) \(station.frequencyText)",
            MPMediaItemPropertyArtist: "NOAA Weather Radio \(station.callSign)",
            MPNowPlayingInfoPropertyIsLiveStream: true,
            MPNowPlayingInfoPropertyPlaybackRate: status == .playing ? 1.0 : 0.0,
        ]
    }

    private func announce(_ text: String) {
        AccessibilityNotification.Announcement(text).post()
    }
}
