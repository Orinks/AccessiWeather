from src.accessiweather.services import national_discussion_scraper

if __name__ == "__main__":
    summaries = national_discussion_scraper.get_national_discussion_summaries()
    print("=== WPC Short Range Summary ===")
    print(summaries["wpc"]["short_range_summary"])
    print("\n=== SPC Day 1 Summary ===")
    print(summaries["spc"]["day1_summary"])
    print("\nAttribution:", summaries["attribution"])
