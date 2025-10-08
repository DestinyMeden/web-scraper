# advanced_safe_scraper.py
"""
Advanced, *safe* educational web scraper.

Purpose:
- Teach students scraping techniques and how to collect non-sensitive, public page data.
- NOT for vulnerability scanning, fuzzing, or exploitation.
- Respects robots.txt, rate limits, and same-domain constraints by default.

Use only on sites you own or explicitly have permission to test (e.g., TryHackMe/HackTheBox **lab machines** as permitted).

Dependencies:
- requests
- beautifulsoup4
- pandas (optional, only if you want CSV output via DataFrame; not required)
"""

import requests
from bs4 import BeautifulSoup, Comment
from urllib.parse import urljoin, urlparse
import urllib.robotparser
import time
import json
import csv
import os
import re
from typing import List, Dict, Optional

USER_AGENT = "EduSafeScraper/1.0 (+https://example.com/contact)"

# ---------- Utility helpers ----------

def politely_wait(delay_seconds: float):
    if delay_seconds > 0:
        time.sleep(delay_seconds)

def allowed_by_robots(target_url: str, user_agent: str = USER_AGENT) -> bool:
    """Check robots.txt for the site root."""
    parsed = urlparse(target_url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    rp = urllib.robotparser.RobotFileParser()
    try:
        rp.set_url(robots_url)
        rp.read()
        return rp.can_fetch(user_agent, target_url)
    except Exception:
        # If robots.txt cannot be fetched, default to disallowing automated scraping in this safe tool.
        return False

def normalize_url(base: str, link: str) -> str:
    try:
        return urljoin(base, link)
    except Exception:
        return link

def same_domain(u1: str, u2: str) -> bool:
    try:
        return urlparse(u1).netloc == urlparse(u2).netloc
    except Exception:
        return False

# ---------- Extraction helpers ----------

def extract_forms(soup: BeautifulSoup) -> List[Dict]:
    forms = []
    for form in soup.find_all("form"):
        form_info = {
            "action": form.get("action"),
            "method": form.get("method", "get").lower(),
            "inputs": []
        }
        for inp in form.find_all(["input", "textarea", "select"]):
            input_info = {
                "tag": inp.name,
                "type": inp.get("type"),
                "name": inp.get("name"),
                "id": inp.get("id"),
                "placeholder": inp.get("placeholder"),
                "value": inp.get("value")
            }
            form_info["inputs"].append(input_info)
        forms.append(form_info)
    return forms

def extract_comments(soup: BeautifulSoup) -> List[str]:
    comments = []
    for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
        text = comment.strip()
        if text:
            comments.append(text)
    return comments

def extract_meta(soup: BeautifulSoup) -> Dict[str, str]:
    meta = {}
    for tag in soup.find_all("meta"):
        name = tag.get("name") or tag.get("property") or tag.get("http-equiv")
        content = tag.get("content")
        if name and content:
            meta[name] = content
    return meta

def extract_assets(soup: BeautifulSoup, base_url: str) -> Dict[str, List[str]]:
    assets = {"scripts": [], "stylesheets": [], "images": [], "links": []}
    for s in soup.find_all("script"):
        src = s.get("src")
        if src:
            assets["scripts"].append(normalize_url(base_url, src))
    for l in soup.find_all("link", rel=lambda x: x and 'stylesheet' in x):
        href = l.get("href")
        if href:
            assets["stylesheets"].append(normalize_url(base_url, href))
    for img in soup.find_all("img"):
        if img.get("src"):
            assets["images"].append(normalize_url(base_url, img.get("src")))
    for a in soup.find_all("a", href=True):
        assets["links"].append(normalize_url(base_url, a["href"]))
    return assets

# ---------- Main scraping logic ----------

class SafeScraper:
    def __init__(self,
                 start_url: str,
                 allowed_selectors: Optional[List[str]] = None,
                 regex_filter: Optional[str] = None,
                 max_pages: int = 50,
                 delay: float = 1.0,
                 same_domain_only: bool = True,
                 respect_robots: bool = True,
                 user_agent: str = USER_AGENT):
        self.start_url = start_url
        self.allowed_selectors = allowed_selectors or []
        self.regex_filter = re.compile(regex_filter) if regex_filter else None
        self.max_pages = max_pages
        self.delay = delay
        self.same_domain_only = same_domain_only
        self.respect_robots = respect_robots
        self.user_agent = user_agent

        self.session = requests.Session()
        self.session.headers.update({"User-Agent": self.user_agent})
        self.visited = set()
        self.to_visit = [start_url]
        self.results = []

        if self.respect_robots and not allowed_by_robots(start_url, user_agent=self.user_agent):
            raise RuntimeError(f"Blocked by robots.txt for {start_url} — Aborting (respect_robots=True).")

    def fetch(self, url: str) -> Optional[requests.Response]:
        try:
            resp = self.session.get(url, timeout=15, allow_redirects=True)
            return resp
        except requests.RequestException as e:
            print(f"[!] Request error for {url}: {e}")
            return None

    def process_page(self, url: str, response: requests.Response):
        soup = BeautifulSoup(response.text, "html.parser")
        page_data = {
            "url": url,
            "status_code": response.status_code,
            "title": (soup.title.string.strip() if soup.title else ""),
            "headers": {k: v for k, v in response.headers.items()},
            "cookies": {c.name: c.value for c in response.cookies},
            "meta": extract_meta(soup),
            "forms": extract_forms(soup),
            "comments": extract_comments(soup),
            "assets": extract_assets(soup, url),
            "selected_texts": [],
        }

        # If selectors were provided, extract matching texts
        for sel in self.allowed_selectors:
            try:
                nodes = soup.select(sel)
                texts = [n.get_text(strip=True) for n in nodes if n.get_text(strip=True)]
                if texts:
                    page_data["selected_texts"].append({"selector": sel, "matches": texts})
            except Exception as e:
                print(f"[!] Selector error '{sel}' on {url}: {e}")

        # If regex filter provided, find matches in visible text
        if self.regex_filter:
            page_text = soup.get_text(separator=" ", strip=True)
            matches = self.regex_filter.findall(page_text)
            page_data["regex_matches"] = matches

        self.results.append(page_data)

        # Queue same-domain links if allowed
        for link in page_data["assets"]["links"]:
            if link not in self.visited and link not in self.to_visit:
                if self.same_domain_only and not same_domain(self.start_url, link):
                    continue
                if self.respect_robots and not allowed_by_robots(link, user_agent=self.user_agent):
                    continue
                self.to_visit.append(link)

    def run(self):
        while self.to_visit and len(self.visited) < self.max_pages:
            url = self.to_visit.pop(0)
            if url in self.visited:
                continue
            print(f"[+] Fetching ({len(self.visited)+1}/{self.max_pages}): {url}")
            resp = self.fetch(url)
            if resp is None:
                self.visited.add(url)
                politely_wait(self.delay)
                continue
            self.process_page(url, resp)
            self.visited.add(url)
            politely_wait(self.delay)

    def save_json(self, path: str):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.results, f, ensure_ascii=False, indent=2)

    def save_csv(self, path: str):
        # Flatten results into rows for CSV; keep JSON for complex fields
        rows = []
        for r in self.results:
            rows.append({
                "url": r.get("url"),
                "status_code": r.get("status_code"),
                "title": r.get("title"),
                "headers": json.dumps(r.get("headers", {})),
                "meta": json.dumps(r.get("meta", {})),
                "forms": json.dumps(r.get("forms", [])),
                "assets": json.dumps(r.get("assets", {})),
                "selected_texts": json.dumps(r.get("selected_texts", [])),
                "regex_matches": json.dumps(r.get("regex_matches", [])) if r.get("regex_matches") else ""
            })
        with open(path, "w", newline='', encoding="utf-8") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=rows[0].keys() if rows else [])
            if rows:
                writer.writeheader()
                for row in rows:
                    writer.writerow(row)

# ---------- CLI / interactive input ----------

def get_user_config():
    print("=== Edu Safe Scraper (educational) ===")
    start_url = input("Enter starting URL (must include http/https): ").strip()
    sel_input = input("Enter CSS selectors to capture (comma-separated), or leave blank: ").strip()
    selectors = [s.strip() for s in sel_input.split(",")] if sel_input else []
    regex = input("Enter an optional regex to search page text (or leave blank): ").strip() or None
    max_pages = input("Max pages (default 20): ").strip()
    max_pages = int(max_pages) if max_pages.isdigit() else 20
    delay = input("Delay between requests in seconds (default 1.0): ").strip()
    try:
        delay = float(delay) if delay else 1.0
    except ValueError:
        delay = 1.0
    same_domain_only = input("Restrict to same domain? (y/n, default y): ").strip().lower() != "n"
    respect_robots = input("Respect robots.txt? (y/n, default y): ").strip().lower() != "n"
    out_format = input("Output format (json/csv/both, default json): ").strip().lower() or "json"
    filename = input("Base filename for output (default 'scrape_output'): ").strip() or "scrape_output"
    return {
        "start_url": start_url,
        "selectors": selectors,
        "regex": regex,
        "max_pages": max_pages,
        "delay": delay,
        "same_domain_only": same_domain_only,
        "respect_robots": respect_robots,
        "out_format": out_format,
        "filename": filename
    }

def main():
    cfg = get_user_config()

    # Ethical reminder
    print("\n[!] IMPORTANT: Run this tool only on sites you own or have explicit permission to scan.")
    print("This tool obeys robots.txt when enabled, and it's configured to be conservative by default.\n")

    try:
        scraper = SafeScraper(
            start_url=cfg["start_url"],
            allowed_selectors=cfg["selectors"],
            regex_filter=cfg["regex"],
            max_pages=cfg["max_pages"],
            delay=cfg["delay"],
            same_domain_only=cfg["same_domain_only"],
            respect_robots=cfg["respect_robots"]
        )
    except RuntimeError as e:
        print(f"[ERROR] {e}")
        return

    scraper.run()

    out_base = cfg["filename"]
    if cfg["out_format"] in ("json", "both"):
        json_path = os.path.join("data", out_base + ".json")
        os.makedirs("data", exist_ok=True)
        scraper.save_json(json_path)
        print(f"[+] JSON output saved to {json_path}")
    if cfg["out_format"] in ("csv", "both"):
        csv_path = os.path.join("data", out_base + ".csv")
        os.makedirs("data", exist_ok=True)
        scraper.save_csv(csv_path)
        print(f"[+] CSV output saved to {csv_path}")

if __name__ == "__main__":
    main()
