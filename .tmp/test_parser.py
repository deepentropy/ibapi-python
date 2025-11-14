#!/usr/bin/env python3
"""
Test script to verify the parser works with the example HTML
"""
import json
import re
from bs4 import BeautifulSoup

# Read the example HTML file
with open('example/index.html', 'r', encoding='utf-8') as f:
    html_content = f.read()

soup = BeautifulSoup(html_content, 'html.parser')

# Find all table rows with class 'linebottom'
rows = soup.find_all('tr', class_='linebottom')

downloads = []

for row in rows:
    # Find all cells in the row
    cells = row.find_all('td')

    for cell in cells:
        # Find download link (with .zip or .msi extension)
        link = cell.find('a', href=re.compile(r'(//)?interactivebrokers\.github\.io/downloads/(tws|TWS).*\.(zip|msi)$', re.IGNORECASE))

        if link:
            download_url = link['href']

            # Make sure it's an absolute URL
            if not download_url.startswith('http'):
                if download_url.startswith('//'):
                    download_url = 'https:' + download_url
                else:
                    download_url = 'https://interactivebrokers.github.io' + download_url

            # Extract button text to determine platform
            button_text = link.get_text(strip=True)

            # Determine platform from button text or cell position
            platform = None
            if 'Windows' in button_text or '.msi' in download_url:
                platform = 'Windows'
            elif 'Mac' in button_text or 'Unix' in button_text:
                platform = 'Mac / Unix'

            # Find version and release date in the same cell
            cell_text = cell.get_text()

            version_match = re.search(r'Version:\s*(?:API\s*)?(\d+\.\d+)', cell_text)
            date_match = re.search(r'Release Date:\s*([A-Za-z]+\s+\d+\s+\d{4})', cell_text)

            version = version_match.group(1) if version_match else None
            release_date = date_match.group(1) if date_match else None

            # Find release notes link in the same cell
            release_notes_link = cell.find('a', href=re.compile(r'releasenotes'))
            release_notes_url = None
            if release_notes_link:
                release_notes_url = release_notes_link['href']
                if release_notes_url.startswith('//'):
                    release_notes_url = 'https:' + release_notes_url

            download_info = {
                'url': download_url,
                'version': version,
                'release_date': release_date,
                'platform': platform,
                'release_notes': release_notes_url
            }

            downloads.append(download_info)

print(f"Found {len(downloads)} download(s):\n")

for i, dl in enumerate(downloads, 1):
    print(f"{i}. Platform: {dl['platform']}")
    print(f"   Version: {dl['version']}")
    print(f"   Release Date: {dl['release_date']}")
    print(f"   Download URL: {dl['url']}")
    if dl['release_notes']:
        print(f"   Release Notes: {dl['release_notes']}")
    print()

# Save to JSON
with open('.tmp/download_info_test.json', 'w') as f:
    json.dump(downloads, f, indent=2)
print("Saved to .tmp/download_info_test.json")
