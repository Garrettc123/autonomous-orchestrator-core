"""
MARKET INTELLIGENCE MODULE (PRODUCTION)
=======================================
Real-Time Competitor Reconnaissance.

No simulation. No random numbers.
This module performs live HTTP requests to competitor changelogs and news feeds
to detect actual feature releases.

Dependencies:
    pip install requests beautifulsoup4
"""

import requests
from bs4 import BeautifulSoup
from typing import List, Dict

class MarketIntelligence:
    def __init__(self):
        # Updated targets to more stable URL paths (Main Blogs)
        self.targets = {
            "Kore.ai": "https://kore.ai/blog/",
            "Microsoft": "https://blogs.microsoft.com/ai/",
            "Salesforce": "https://www.salesforce.com/news/press-releases/"
        }
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }

    def scan_landscape(self) -> List[str]:
        """
        Performs ACTUAL HTTP requests to competitor sites to scrape latest updates.
        Returns a list of real, detected feature titles.
        """
        print("🕵️  INTELLIGENCE: Initiating live network scan...")
        detected_features = []

        for competitor, url in self.targets.items():
            try:
                # Real network request with 10s timeout
                response = requests.get(url, headers=self.headers, timeout=10)
                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, 'html.parser')
                    
                    # Generic scraping for article titles
                    # Most blogs use h2 or h3 for titles
                    titles = soup.find_all(['h2', 'h3'], limit=3)
                    
                    found_any = False
                    for title in titles:
                        text = title.get_text().strip()
                        if len(text) > 10: # Filter out empty/short headers
                            print(f"   > {competitor} (Active): '{text[:60]}...'")
                            detected_features.append(f"{competitor}: {text}")
                            found_any = True
                            break # Just get the top one
                    
                    if not found_any:
                         print(f"   > {competitor}: Site Active (200 OK), but no headlines parsed.")
                else:
                    print(f"   > {competitor}: Connection Failed ({response.status_code})")
            except Exception as e:
                print(f"   > {competitor}: Network Error ({str(e)})")

        return detected_features

    def analyze_threat_level(self, features: List[str]) -> str:
        """
        Analyzes real text data to determine threat.
        """
        threat_keywords = ["autonomous", "agent", "self-healing", "zero-config", "level 5"]
        for feature in features:
            if any(keyword in feature.lower() for keyword in threat_keywords):
                return "HIGH - COMPETITOR ADVANCING"
        return "LOW - MAINTENANCE MODE"

if __name__ == "__main__":
    # Test with real network
    intel = MarketIntelligence()
    intel.scan_landscape()
