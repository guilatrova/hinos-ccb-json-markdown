import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import re
import json

BASE_URL = "https://sites.google.com/site/coletaneacantorcristao"


def fetch_menu_links():
    print(f"Fetching {BASE_URL}...")
    response = requests.get(BASE_URL)
    response.raise_for_status()

    soup = BeautifulSoup(response.content, "html.parser")

    # Find all links
    links = []
    # Regex to match links starting with a number (e.g., 001-...)
    pattern = re.compile(r"/(\d{3})-")

    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]
        full_url = urljoin(BASE_URL, href)

        if full_url.startswith(BASE_URL):
            # Check if the path part matches the pattern
            path = full_url.replace(BASE_URL, "")
            match = pattern.search(path)
            if match:
                number = int(match.group(1))
                if number > 0:  # Exclude 000
                    links.append(full_url)

    # Remove duplicates and sort
    links = sorted(list(set(links)))

    print(f"Found {len(links)} hymn links.")

    # Save to file
    with open("links.json", "w") as f:
        json.dump(links, f, indent=2)

    # Print first and last few to verify
    if links:
        print("First 5 links:")
        for link in links[:5]:
            print(link)
        print("...")
        print("Last 5 links:")
        for link in links[-5:]:
            print(link)


if __name__ == "__main__":
    fetch_menu_links()
