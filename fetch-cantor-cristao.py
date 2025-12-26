import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import re
import json
import os
import html
from typing import Final
from concurrent.futures import ThreadPoolExecutor
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

BASE_URL = "https://sites.google.com/site/coletaneacantorcristao"
MAX_THREADS: Final[int] = 3
OUTPUT_DIR = "output/cantor_cristao_html"


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


def get_session():
    session = requests.Session()
    retries = Retry(
        total=5,
        backoff_factor=1,
        status_forcelist=[500, 502, 503, 504],
        allowed_methods=["GET"],
    )
    session.mount("https://", HTTPAdapter(max_retries=retries))
    session.mount("http://", HTTPAdapter(max_retries=retries))
    return session


def fetch_page(url: str, session: requests.Session):
    filename = url.split("/")[-1]
    filepath = os.path.join(OUTPUT_DIR, f"{filename}.html")

    if os.path.exists(filepath):
        print(f"Skipping {filename} (already exists)")
        return

    try:
        print(f"Fetching {url}...")
        response = session.get(url, timeout=30)
        response.raise_for_status()

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(response.text)
    except Exception as e:
        print(f"Failed to fetch {url}: {e}")


def fetch_all_pages():
    if not os.path.exists("links.json"):
        print("links.json not found. Run fetch_menu_links() first.")
        return

    with open("links.json", "r") as f:
        links = json.load(f)

    print(f"Preparing to fetch {len(links)} pages...")

    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    session = get_session()

    with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
        futures = [executor.submit(fetch_page, link, session) for link in links]
        for future in futures:
            future.result()

    print("Done fetching pages.")


def extract_hymn_data(filepath: str):
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    # Extract Title and Number from <title> tag
    soup_title = BeautifulSoup(content, "html.parser")
    title_tag = soup_title.find("title")
    number = 0
    title = "Unknown"

    if title_tag:
        title_text = title_tag.get_text().strip()
        match = re.search(r"Coletânea Cantor Cristão - (\d+) - (.+)", title_text)
        if match:
            number = int(match.group(1))
            title = match.group(2).strip()

    # Extract Lyrics from escaped content
    # Split by &lt;p&gt;
    parts = content.split("&lt;p&gt;")

    lyrics_blocks = []
    verse_counter = 1

    for i, part in enumerate(parts):
        if i == 0:
            continue

        # Truncate at closing tag if present
        end_p_index = part.find("&lt;/p&gt;")
        if end_p_index != -1:
            part_content = part[:end_p_index]
        else:
            part_content = part

        unescaped_content = html.unescape(part_content)

        # Parse fragment
        fragment_soup = BeautifulSoup(unescaped_content, "html.parser")
        text = fragment_soup.get_text().strip()

        # Filter
        if not text:
            continue

        # Filter out metadata
        skip_keywords = [
            "Slides:",
            "Baixar Apresentação",
            "Iniciar SlideShow",
            "Amostra sonora",
            "Kits de voz",
            "Vídeos:",
            "Obs.:",
            "Cifragem",
            "Partituras",
            "Arquivos para edição",
            "Tom original",
            "Soprano:",
            "Contralto:",
            "Tenor:",
            "Baixo:",
            "MIDI(",
            "MP3(",
            "jsaction",
        ]
        if any(x in text for x in skip_keywords):
            continue

        if text.startswith("Letra:") or text.startswith("Música:"):
            continue

        # Extract lines
        lines = [
            l.strip()
            for l in fragment_soup.get_text(separator="\n").split("\n")
            if l.strip()
        ]

        if lines:
            verse_text = "\n".join(lines)
            lyrics_blocks.append(f"[Verse {verse_counter}]\n{verse_text}")
            verse_counter += 1

    full_lyrics = "\n\n".join(lyrics_blocks)

    return {"no": number, "title": title, "lyrics": full_lyrics}


def process_local_files():
    json_dir = "output/cc_json"
    md_dir = "output/cc_markdown"

    # Clear existing directories to avoid stale files
    if os.path.exists(json_dir):
        import shutil

        shutil.rmtree(json_dir)
    if os.path.exists(md_dir):
        import shutil

        shutil.rmtree(md_dir)

    os.makedirs(json_dir, exist_ok=True)
    os.makedirs(md_dir, exist_ok=True)

    html_files = sorted([f for f in os.listdir(OUTPUT_DIR) if f.endswith(".html")])
    print(f"Processing {len(html_files)} HTML files...")

    for filename in html_files:
        filepath = os.path.join(OUTPUT_DIR, filename)
        try:
            data = extract_hymn_data(filepath)

            if data["no"] == 0:
                # Try to extract number from filename if title extraction failed
                # filename format: 001-antífona.html
                try:
                    data["no"] = int(filename.split("-")[0])
                except:
                    print(f"Warning: Could not extract number for {filename}")
                    continue

            # Determine filename with collision handling
            base_name = str(data["no"])
            json_filename = f"{base_name}.json"
            json_path = os.path.join(json_dir, json_filename)

            counter = 2
            while os.path.exists(json_path):
                json_filename = f"{base_name}-{counter}.json"
                json_path = os.path.join(json_dir, json_filename)
                counter += 1

            # Corresponding markdown filename
            md_filename = json_filename.replace(".json", ".md")
            md_path = os.path.join(md_dir, md_filename)

            # Save JSON
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            # Save Markdown
            md_content = f"# {data['no']}. {data['title']}\n\n{data['lyrics']}"
            with open(md_path, "w", encoding="utf-8") as f:
                f.write(md_content)

        except Exception as e:
            print(f"Error processing {filename}: {e}")

    print("Done processing files.")


if __name__ == "__main__":
    # fetch_menu_links()
    # fetch_all_pages()
    process_local_files()
