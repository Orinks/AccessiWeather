"""Stream URL provider for NOAA Weather Radio stations."""

from __future__ import annotations


class StreamURLProvider:
    """
    Provides streaming URLs for NOAA Weather Radio stations.

    Maps station call signs to audio stream URLs from various aggregator
    services. Supports multiple URL sources per station for fallback.
    """

    # Real stream URLs sourced from weatherUSA.net/radio and volunteer providers.
    _STREAM_URLS: dict[str, list[str]] = {
        # Alabama
        "KEC61": ["https://radio.weatherusa.net/NWR/KEC61_2.mp3"],
        # Arizona
        "WWG42": ["https://wxr.gwes-cdn.net/WWG42", "https://wxradio.org/AZ-Globe-WWG42"],
        "WWG41": [
            "https://wxr.gwes-cdn.net/WWG41",
            "https://wxradio.org/AZ-PaysonGilaCountyN-WWG41",
        ],
        "KEC94": ["https://wxr.gwes-cdn.net/KEC94", "https://wxradio.org/AZ-Phoenix-KEC94"],
        # California
        "WNG659": ["https://wxr.gwes-cdn.net/WNG659"],
        "KIH62": ["https://radio.weatherusa.net/NWR/KIH62_2.mp3"],
        "KWO37": ["https://wxr.gwes-cdn.net/KWO37"],
        "WWF64": ["https://wxradio.org/CA-MontereyMarine-WWF64"],
        "KEC49": ["https://wxradio.org/CA-Monterey-KEC49"],
        # Colorado
        "KWN54": ["https://wxr.gwes-cdn.net/KWN54", "https://radio.weatherusa.net/NWR/KWN54.mp3"],
        # Connecticut
        "WXJ42": ["https://wxradio.org/CT-Meriden-WXJ42"],
        # Florida
        "KIH26": ["https://wxradio.org/FL-DaytonaBeach-KIH26"],
        "WZ2531": ["https://wxr.gwes-cdn.net/WZ2531"],
        "KHB39": ["https://wxr.gwes-cdn.net/KHB39"],
        "KEC38": ["https://wxradio.org/FL-Largo-KEC38"],
        "KHB34": ["https://wxr.gwes-cdn.net/KHB34"],
        "KIH63": ["https://wxradio.org/FL-Orlando-KIH63"],
        "WNG522": ["https://wxradio.org/FL-Palatka-WNG522"],
        "WNG663": ["https://wxr.gwes-cdn.net/WNG663"],
        "KIH24": [
            "https://wxradio.org/FL-Tallahassee-KIH24",
            "http://wxradio.dyndns.org:8000/FL-Tallahassee-KIH24",
        ],
        "KHB32": ["https://wxradio.org/FL-TampaBay-KHB32"],
        # Georgia
        "WXK56": ["https://wxradio.org/GA-Athens-WXK56"],
        "KEC80": ["https://wxr.gwes-cdn.net/KEC80-ALT", "https://wxradio.org/GA-Atlanta-KEC80"],
        "WXM32": [
            "https://wxradio.org/AL-Columbus-WXM32",
            "https://radio.weatherusa.net/NWR/WXM32.mp3",
        ],
        # Hawaii
        "WWG75": ["https://wxradio.org/HI-Maui-WWG75"],
        # Iowa
        "WXL57": ["https://radio.weatherusa.net/NWR/WXL57.mp3"],
        "WXL62": ["https://wxradio.org/IA-Sioux_City-WXL62"],
        # Illinois
        "WXJ76": ["https://wxradio.org/IL-Champaign-WXJ76"],
        "KZZ66": ["https://wxradio.org/IL-Galesburg-KZZ66"],
        "KZZ58": ["https://wxradio.org/IL-Kankakee-KZZ58"],
        "KZZ81": ["https://wxr.gwes-cdn.net/KZZ81"],
        "WXM49": ["https://wxradio.org/IL-Marion-WXM49-ALT1"],
        "WXJ71": ["https://wxradio.org/IL-Peoria-WXJ71"],
        "KXI58": ["https://wxradio.org/IL-Plano-KXI58"],
        "WXJ73": ["https://wxradio.org/IL-QuadCities-WXJ73"],
        # Indiana
        "KEC74": ["https://wxradio.org/IN-Indianapolis-KEC74"],
        "KIG76": ["https://wxr.gwes-cdn.net/KIG76"],
        # Kansas
        "WXK91": ["https://wxradio.org/KS-Topeka-WXK91-alt1"],
        # Kentucky
        "WZ2523": ["https://wxradio.org/KY-Frankfort-WZ2523"],
        "KZZ48": ["https://wxradio.org/KY-Owenton-KZZ48"],
        # Louisiana
        "WXJ96": [
            "https://wxradio.org/LA-Monroe-WXJ96",
            "https://radio.weatherusa.net/NWR/WXJ96_2.mp3",
        ],
        "WXJ97": [
            "https://wxr.gwes-cdn.net/WXJ97",
            "https://wxradio.org/LA-Shreveport-WXJ97",
            "https://wxradio.org/LA-Shreveport-WXJ97-alt1",
        ],
        # Maine
        "WSM60": ["https://wxradio.org/ME-Dresden-WSM60"],
        # Maryland
        "WXM42": [
            "https://wxradio.org/MD-Hagerstown-WXM42",
            "https://noaa-manassas-radio.from-va.com/Hagerstown.mp3",
        ],
        # Massachusetts
        "KHB35": ["https://radio.weatherusa.net/NWR/KHB35_3.mp3"],
        "KEC73": ["https://wxradio.org/MA-Bourne/Hyannis-KEC73"],
        "WXL93": ["https://wxradio.org/MA-Worcester-WXL93"],
        # Michigan
        "KEC63": ["https://radio.weatherusa.net/NWR/KEC63.mp3", "https://wxr.gwes-cdn.net/KEC63"],
        "KIH29": ["https://wxr.gwes-cdn.net/KIH29", "https://wxradio.org/MI-Clio-KIH29"],
        "WWF36": ["https://wxradio.org/MI-Hesperia-WWF36"],
        "WWF34": [
            "https://icecast.wxstream.org/NWR/WWF34",
            "https://wxr.gwes-cdn.net/WWF34",
            "https://wxradio.org/MI-Plainwell-WWF34",
        ],
        "KZZ33": [
            "https://wxr.gwes-cdn.net/KZZ33",
            "https://wxradio.org/MI-MountPleasant-KZZ33",
            "https://wxradio.org/MI-MountPleasant-KZZ33-alt2",
            "https://noaaradio.herseyweather.com/MI-MountPleasant-KZZ33-alt1",
        ],
        "WXK81": ["https://wxr.gwes-cdn.net/WXK81", "https://icecast.wxstream.org/NWR/WXK81"],
        "KXI33": ["https://wxr.gwes-cdn.net/KXI33", "https://wxradio.org/MI-WestBranch-KXI33"],
        "WXN99": [
            "https://wxr.gwes-cdn.net/WXN99-Alt",
            "https://radio.weatherusa.net/NWR/WXN99.mp3",
        ],
        "WNG672": [
            "https://wxradio.org/MI-WolfLake-WNG672",
            "https://noaaradio.herseyweather.com/MI-WolfLake-WNG672-alt1",
        ],
        "WZ2560": ["https://wxr.gwes-cdn.net/WZ2560"],
        # Minnesota
        "KEC65": ["https://radio.weatherusa.net/NWR/KEC65.mp3"],
        "WXM99": [
            "https://wxr.gwes-cdn.net/WXM99",
            "https://wxr.bemidjiwx.org/WXM99",
            "https://wxradio.org/MN-Bemidji-WXM99",
        ],
        "WNG676": [
            "https://radio.weatherusa.net/NWR/WNG676.mp3",
            "http://wxradio.dyndns.org:8000/NWR/WNG676.mp3",
        ],
        "WXJ86": ["https://wxradio.org/MN-LaCrescent-WXJ86"],
        "WWG98": ["https://wxr.gwes-cdn.net/WWG98", "https://wxr.bemidjiwx.org/WWG98"],
        # Missouri
        "KID77": [
            "https://wxr.gwes-cdn.net/KID77",
            "https://wxradio.org/MO-KansasCity-KID77",
            "https://radio.weatherusa.net/NWR/KID77_3.mp3",
        ],
        "KDO89": ["https://wxradio.org/MO-StLouis-KDO89"],
        "WXL46": ["https://wxr.gwes-cdn.net/WXL46", "https://wxradio.org/MO-Springfield-WXL46"],
        # Montana
        "WXL25": ["https://wxr.gwes-cdn.net/WXL25"],
        # North Dakota
        "WXL78": ["https://wxradio.org/ND-Bismarck-WXL78"],
        "WWF83": ["https://wxr.gwes-cdn.net/WWF83", "https://wxradio.org/ND-GrandForks-WWF83"],
        "WXM38": ["https://wxr.gwes-cdn.net/WXM38"],
        # Nebraska
        "KZZ69": ["https://radio.weatherusa.net/NWR/KZZ69.mp3"],
        "WXL74": ["https://wxradio.org/NE-GrandIsland-WXL74"],
        "WXM20": [
            "https://wxradio.org/NE-Lincoln-WXM20-alt2",
            "https://wxradio.org/NE-Lincoln-WXM20-alt1",
        ],
        "KIH61": [
            "https://radio.weatherusa.net/NWR/KIH61.mp3",
            "https://wxr.gwes-cdn.net/KIH61",
            "https://wxradio.org/NE-Omaha-KIH61-A",
        ],
        "WXL67": ["https://wxradio.org/NE-Scottsbluff-WXL67"],
        # Nevada
        "WWG20": ["https://radio.weatherusa.net/NWR/WWG20.mp3"],
        "WXK58": ["https://radio.weatherusa.net/NWR/WXK58.mp3"],
        # New Mexico
        "WXJ37": ["https://wxr.gwes-cdn.net/WXJ37", "https://radio.weatherusa.net/NWR/WXJ37.mp3"],
        # New York
        "KWO35": [
            "https://wxr.gwes-cdn.net/KWO35",
            "https://wxradio.org/NY-NewYorkCity-KWO35",
            "https://www.saucci.net:8443/audio3.ogg",
        ],
        "WXL34": ["https://wxradio.org/NY-Albany-WXL34"],
        "KEB98": ["https://radio.weatherusa.net/NWR/KEB98.mp3"],
        "WZ2536": ["https://wxradio.org/NY-Lyons-WZ2536"],
        "WXM45": ["https://wxradio.org/NY-Middleville-WXM45-alt1"],
        "KHA53": ["https://wxradio.org/NY-Rochester-KHA53"],
        "WXL31": [
            "https://wxradio.org/NY-Syracuse-WXL31",
            "https://wxradio.org/NY-Syracuse-WXL31-alt1",
        ],
        # Ohio
        "KDO94": ["https://radio.weatherusa.net/NWR/KDO94.mp3"],
        "KIG86": [
            "https://wxradio.org/OH-Columbus-KIG86",
            "https://radio.weatherusa.net/NWR/KIG86.mp3",
        ],
        "WNG698": ["https://wxradio.org/OH-Grafton-WNG698"],
        "WWG57": ["https://wxradio.org/OH-Mansfield-WWG57"],
        "WXJ93": [
            "https://wxradio.org/OH-Lima-WXJ93",
            "https://wxradio.org/OH-Lima-WXJ93-alt1",
            "https://wxradio.org/OH-Lima-WXJ93-alt2",
        ],
        "WXL51": ["https://wxr.gwes-cdn.net/WXL51", "https://wxradio.org/OH-Toledo-WXL51"],
        # Oklahoma
        "WXK85": [
            "https://wxradio.org/OK-OklahomaCity-WXK85",
            "https://radio.weatherusa.net/NWR/WXK85.mp3",
        ],
        "WXK86": [
            "https://wxradio.org/OK-Lawton-WXK86",
            "https://radio.weatherusa.net/NWR/WXK86.mp3",
        ],
        "KIH27": ["https://wxradio.org/OK-Tulsa-KIH27"],
        # Pennsylvania
        "WXL39": ["https://wxr.gwes-cdn.net/WXL39"],
        "KIH28": [
            "https://wxr.gwes-cdn.net/KIH28",
            "https://wxradio.org/PA-Philadelphia-KIH28",
        ],
        "WXL40": ["https://wxradio.org/PA-Harrisburg-WXL40"],
        "WNG704": ["https://wxradio.org/PA-HiberniaPark-WNG704"],
        "WXL43": ["https://wxradio.org/PA-WilkesBarre-WXL43"],
        # South Carolina
        "WXJ21": ["https://wxr.gwes-cdn.net/WXJ21", "https://wxradio.org/SC-Greenville-WXJ21"],
        "KEC85": ["https://wxr.gwes-cdn.net/KEC85", "https://wxradio.org/SC-Savannah-KEC85"],
        # Tennessee
        "WXK49": ["https://usa10.fastcast4u.com:3210/1"],
        "WXK63": ["https://radio.weatherusa.net/NWR/WXK63.mp3"],
        "KIG79": ["https://wxr.gwes-cdn.net/KIG79"],
        # Texas
        "WXK38": ["https://radio.weatherusa.net/NWR/WXK38_2.mp3"],
        "WXK27": ["https://wxradio.org/TX-Austin-WXK27"],
        "WXK30": ["https://wxr.gwes-cdn.net/WXK30"],
        "KXI87": ["https://wxr.gwes-cdn.net/KXI87", "https://radio.weatherusa.net/NWR/KXI87.mp3"],
        "KEC56": ["https://wxradio.org/TX-Dallas-KEC56"],
        "KEC55": ["https://wxr.gwes-cdn.net/KEC55", "https://radio.weatherusa.net/NWR/KEC55_2.mp3"],
        "KHB40": ["https://wxradio.org/TX-Galveston-KHB40"],
        "KGG68": ["https://wxr.gwes-cdn.net/KGG68", "https://radio.weatherusa.net/NWR/KGG68.mp3"],
        "WXK23": ["https://radio.weatherusa.net/NWR/WXK23.mp3"],
        "KWN34": ["https://radio.weatherusa.net/NWR/KWN34.mp3"],
        "WXK36": [
            "https://wxradio.org/TX-Tyler-WXK36",
            "https://radio.weatherusa.net/NWR/WXK36_2.mp3",
            "https://wxradio.org/TX-Tyler-WXK36-alt1",
            "https://wxradio.org/TX-Tyler-WXK36-alt2",
        ],
        "WXK35": ["https://radio.weatherusa.net/NWR/EW6308.mp3"],
        # Virginia
        "KHB36": [
            "https://wxr.gwes-cdn.net/KHB36",
            "https://stream.mikev.com/khb36.mp3",
            "https://wxradio.org/VA-Manassas-KHB36",
        ],
        "KHB37": [
            "https://wxr.gwes-cdn.net/KHB37",
            "https://wxradio.org/VA-Norfolk-KHB37",
            "https://radio.weatherusa.net/NWR/KHB37_3.mp3",
        ],
        # Washington
        "KHB60": ["https://wxradio.bobc.io/stream/KHB60", "https://wxr.gwes-cdn.net/KHB60"],
        "WWG24": [
            "https://wxradio.org/WA-PugetSoundMarine-WWG24",
            "https://wxradio.bobc.io/stream/WWG24",
            "https://wxr.gwes-cdn.net/WWG24",
        ],
        "WWF56": ["https://radio.weatherusa.net/NWR/WWF56_2.mp3"],
        # West Virginia
        "WXM71": ["https://wxradio.org/WV-Beckley-WXM71"],
        "WXJ84": ["https://wxr.gwes-cdn.net/WXJ84"],
        "WXM74": ["https://wxr.gwes-cdn.net/WXM74"],
        # Wisconsin
        "KZZ78": ["https://wxradio.org/WI-Ashland-KZZ78"],
        "KIG65": ["https://wxradio.org/WI-GreenBay-KIG65"],
        "WXJ88": [
            "https://wxradio.org/WI-Menomonie-WXJ88",
            "https://radio.weatherusa.net/NWR/WXJ88.mp3",
            "https://wxradio.org/WI-Menomonie-WXJ88-alt1",
        ],
        "WNG553": ["https://wxradio.org/WI-Wausaukee-WNG553"],
        "KGG95": [
            "https://wxradio.org/MN-Winona-KGG95",
            "https://radio.weatherusa.net/NWR/KGG95.mp3",
        ],
        "KZZ77": ["https://wxradio.org/WI-Withee-KZZ77"],
        # Canada - Alberta
        "XLF339": ["https://wxradio.org/AB-Calgary-XLF339"],
        "XLM572": ["https://wxradio.org/AB-Edmonton-XLM572"],
        # Canada - Ontario
        "XMJ316": ["https://wxradio.org/ON-Collingwood-XMJ316"],
        "XMJ225": ["https://wxradio.org/ON-Toronto-XMJ225"],
    }

    # Default URL pattern template using Broadcastify CDN.
    _DEFAULT_PATTERN = "https://broadcastify.cdnstream1.com/noaa/{call_sign}"

    def __init__(
        self,
        custom_urls: dict[str, list[str]] | None = None,
        use_fallback: bool = True,
    ) -> None:
        """
        Initialize the stream URL provider.

        Args:
            custom_urls: Optional dictionary of call_sign -> list of URLs
                to override or supplement the built-in database.
            use_fallback: Whether to generate a fallback URL from the default
                pattern when no known URL exists for a station.

        """
        self._urls: dict[str, list[str]] = dict(self._STREAM_URLS)
        if custom_urls:
            for call_sign, urls in custom_urls.items():
                self._urls[call_sign.upper()] = urls
        self._use_fallback = use_fallback

    def get_stream_url(self, call_sign: str) -> str | None:
        """
        Get the primary stream URL for a station.

        Args:
            call_sign: The station call sign (case-insensitive).

        Returns:
            The primary stream URL string, or None if no URL is available.

        """
        urls = self.get_stream_urls(call_sign)
        return urls[0] if urls else None

    def get_stream_urls(self, call_sign: str) -> list[str]:
        """
        Get all available stream URLs for a station.

        Returns multiple URLs for fallback purposes. The first URL in the
        list is considered the primary/preferred source.

        Args:
            call_sign: The station call sign (case-insensitive).

        Returns:
            A list of stream URL strings. Empty list if no URLs are available.

        """
        normalized = call_sign.upper().strip()
        if not normalized:
            return []

        urls = self._urls.get(normalized)
        if urls:
            return list(urls)

        if self._use_fallback:
            return [self._DEFAULT_PATTERN.format(call_sign=normalized)]

        return []

    def has_known_url(self, call_sign: str) -> bool:
        """
        Check if a station has a known (non-fallback) stream URL.

        Args:
            call_sign: The station call sign (case-insensitive).

        Returns:
            True if the station has known stream URLs in the database.

        """
        return call_sign.upper().strip() in self._urls
