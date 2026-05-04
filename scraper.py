# ==========================
# HVAC SCRAPER V6.9 (Podium + Chat Fix)
# ==========================

import pandas as pd
import re
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin
from playwright.sync_api import sync_playwright

INPUT_FILE = "input.csv"
OUTPUT_FILE = "results.csv"

SUBPAGES = [
    "",
    "/contact",
    "/contact-us",
    "/schedule-service",
    "/request-service",
    "/estimate",
    "/quote"
]

# Expanded vendors
TEXT_CHAT_VENDORS = {
    "podium": "Podium",
    "hatch": "Hatch",
    "birdeye": "Birdeye",
    "intercom": "Intercom",
    "drift": "Drift",
    "tawk": "Tawk",
    "livechat": "LiveChat",
    "zendesk": "Zendesk",
    "housecallpro": "HousecallPro Chat",
    "servicetitan": "ServiceTitan Chat"
}

BOOKING_VENDORS = {
    "calendly": "Calendly",
    "daysmart": "DaySmart",
    "housecallpro": "HousecallPro",
    "servicetitan": "ServiceTitan",
    "jobber": "Jobber"
}

PHONE_REGEX = r"\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}"


# --------------------------
# Helpers
# --------------------------

def clean_domain(value):
    if value.startswith("http"):
        return urlparse(value).netloc.replace("www.", "")
    return value.replace("www.", "").strip("/")


def has_phone(text):
    return re.search(PHONE_REGEX, text) is not None


# --------------------------
# Fetch with network tracking
# --------------------------

def fetch_with_browser(url):
    detected_network = []

    def handle_request(request):
        detected_network.append(request.url.lower())

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        page.on("request", handle_request)

        try:
            page.goto(url, timeout=15000)
            page.wait_for_load_state("networkidle")

            # KEY FIX: allow async widgets (Podium etc.) to load
            page.wait_for_timeout(3000)

            html = page.content()

        except:
            browser.close()
            return "", []

        browser.close()
        return html, detected_network


# --------------------------
# Detection Logic
# --------------------------

def detect_form(soup):
    if soup.find("form"):
        return True, "High"

    for iframe in soup.find_all("iframe"):
        src = iframe.get("src", "").lower()
        if "form" in src or "contact" in src:
            return True, "Medium"

    if len(soup.find_all("input")) >= 2:
        return True, "Low"

    return False, ""


def detect_text_chat(html, network_calls, soup):
    html_low = html.lower()

    # HIGH: vendor detected in HTML or network
    for key, name in TEXT_CHAT_VENDORS.items():
        if key in html_low:
            return True, name, "High"

        for url in network_calls:
            if key in url:
                return True, name, "High"

    # MEDIUM: SMS link
    for a in soup.find_all("a", href=True):
        if a["href"].lower().startswith("sms:"):
            return True, "iMessage", "Medium"

    # LOW: keywords
    text = soup.get_text(" ", strip=True).lower()
    if "text us" in text or "message us" in text:
        return True, "Unknown", "Low"

    return False, "", ""


def detect_booking(html, soup):
    html_low = html.lower()
    text = soup.get_text(" ", strip=True).lower()

    # HIGH: booking URLs
    for a in soup.find_all("a", href=True):
        href = a["href"].lower()
        if any(x in href for x in ["calendar", "booking", "appointments"]):
            return True, "Detected", "High"

    # MEDIUM: vendor present
    for key, name in BOOKING_VENDORS.items():
        if key in html_low:
            return True, name, "Medium"

    # LOW: keyword
    if "schedule service" in text or "book now" in text:
        return True, "Unknown", "Low"

    return False, "", ""


def find_links(soup, base_url):
    links = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if any(x in href.lower() for x in ["contact", "schedule", "request"]):
            links.append(urljoin(base_url, href))
    return list(set(links))


# --------------------------
# Main
# --------------------------

def analyze(domain):
    domain = clean_domain(domain)

    pages = [f"https://{domain}{p}" for p in SUBPAGES]
    visited = set()

    form, form_conf, form_url = False, "", ""
    text, text_vendor, text_conf = False, "", ""
    booking, booking_vendor, booking_conf = False, "", ""
    phone = False

    for url in pages:
        if url in visited:
            continue
        visited.add(url)

        html, network_calls = fetch_with_browser(url)
        if not html:
            continue

        soup = BeautifulSoup(html, "lxml")
        text_content = soup.get_text(" ", strip=True)

        if has_phone(text_content):
            phone = True

        if not form:
            f, conf = detect_form(soup)
            if f:
                form, form_conf, form_url = True, conf, url

        if not text:
            t, vendor, conf = detect_text_chat(html, network_calls, soup)
            if t:
                text, text_vendor, text_conf = True, vendor, conf

        if not booking:
            b, vendor, conf = detect_booking(html, soup)
            if b:
                booking, booking_vendor, booking_conf = True, vendor, conf

        if url.endswith(domain):
            pages.extend(find_links(soup, url))

    return {
        "Domain": domain,
        "Phone": phone,

        "FormCapability": form,
        "FormConfidence": form_conf,
        "FormURL": form_url,

        "TextCapability": text,
        "TextVendor": text_vendor,
        "TextConfidence": text_conf,

        "BookingCapability": booking,
        "BookingVendor": booking_vendor,
        "BookingConfidence": booking_conf
    }


def main():
    df = pd.read_csv(INPUT_FILE)

    results = []
    for _, row in df.iterrows():
        print("Checking:", row["domain"])
        results.append(analyze(row["domain"]))

    pd.DataFrame(results).to_csv(OUTPUT_FILE, index=False)
    print("Saved to results.csv")


if __name__ == "__main__":
    main()