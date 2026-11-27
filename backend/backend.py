import json
import re
from html import unescape
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup, NavigableString, Tag
from flask import Flask, jsonify, request
from flask_cors import CORS

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

RESPONSIBILITY_HINTS = (
    "responsibilit",
    "priorit",
    "what you",
    "what you'll",
    "what you’ll",
    "duties",
    "the role",
    "how you'll",
    "how you’ll",
    "you'll do",
    "you’ll do",
    "impact",
    "you will do",
)
QUALIFICATION_HINTS = (
    "qualification",
    "requirement",
    "ideal candidate",
    "who you are",
    "what you'll need",
    "what you’ll need",
    "minimum qualif",
    "basic qualif",
    "preferred",
    "nice to have",
    "about you",
    "looking for",
    "to be eligible",
    "what we require",
    "what we value",
    "what we are looking",
)
PAY_HINTS = ("pay", "salary", "compensation", "stipend", "wage")
SKIP_LABELS = {
    "apply",
    "apply now",
    "apply for this job",
    "back to jobs",
    "share",
    "login",
    "sign in",
}


def clean(text):
    text = unescape(text or "")
    text = text.replace("\xa0", " ").replace("\u200b", "")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def one_line(text):
    return re.sub(r"\s+", " ", clean(text))


def fetch_html(url):
    response = requests.get(url, headers=HEADERS, timeout=25)
    response.raise_for_status()
    return response.text, response.url


def meta_content(soup, *keys):
    for key in keys:
        tag = soup.find("meta", property=key) or soup.find("meta", attrs={"name": key})
        if tag and tag.get("content"):
            return one_line(tag["content"])
    return None


def flatten_jsonld(data):
    if isinstance(data, list):
        for item in data:
            yield from flatten_jsonld(item)
    elif isinstance(data, dict):
        if data.get("@graph"):
            yield from flatten_jsonld(data["@graph"])
        yield data


def iter_jsonld(soup):
    for tag in soup.find_all("script", attrs={"type": re.compile(r"ld\+json", re.I)}):
        raw = tag.string or tag.get_text()
        if not raw or not raw.strip():
            continue
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        yield from flatten_jsonld(data)


def is_job_posting(node):
    kind = node.get("@type", "")
    if isinstance(kind, list):
        return any("JobPosting" in str(item) for item in kind)
    return "JobPosting" in str(kind)


def value_text(value):
    if value is None or value is False:
        return None
    if isinstance(value, str):
        text = one_line(value)
        return text or None
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, list):
        parts = [value_text(item) for item in value]
        parts = [part for part in parts if part]
        return "; ".join(parts) if parts else None
    if isinstance(value, dict):
        if value.get("address"):
            return value_text(value["address"])
        if value.get("name"):
            return value_text(value["name"])
        if "@value" in value or "value" in value:
            unit = value.get("unitText") or ""
            amount = value.get("@value", value.get("value"))
            text = value_text(amount)
            return f"{text} {unit}".strip() if text else None
        bits = []
        for key in ("streetAddress", "addressLocality", "addressRegion", "postalCode", "addressCountry"):
            bit = value_text(value.get(key))
            if bit:
                bits.append(bit)
        if bits:
            return ", ".join(bits)
    return None


def html_to_text(value):
    if not value:
        return ""
    if "<" in value and ">" in value:
        fragment = BeautifulSoup(value, "lxml")
        return clean(fragment.get_text("\n", strip=True))
    return clean(value)


def salary_text(node):
    salary = node.get("baseSalary") or node.get("estimatedSalary")
    if isinstance(salary, list):
        parts = [salary_text({"baseSalary": item}) for item in salary]
        return [part for part in parts if part]
    if isinstance(salary, str):
        text = one_line(salary)
        return [text] if text else []
    if not isinstance(salary, dict):
        return []
    currency = salary.get("currency") or ""
    value = salary.get("value") if "value" in salary else salary
    if isinstance(value, dict):
        low = value.get("minValue")
        high = value.get("maxValue")
        amount = value.get("value") or value.get("@value")
        unit = value.get("unitText") or ""
        if low and high:
            text = f"{currency} {low}–{high} {unit}".strip()
        elif amount:
            text = f"{currency} {amount} {unit}".strip()
        else:
            text = value_text(value) or ""
        text = one_line(text)
        return [text] if text else []
    text = value_text(salary)
    return [text] if text else []


def from_jsonld(soup):
    for node in iter_jsonld(soup):
        if not is_job_posting(node):
            continue
        return {
            "title": value_text(node.get("title")),
            "company": value_text(node.get("hiringOrganization")),
            "location": value_text(node.get("jobLocation")),
            "employment_type": value_text(node.get("employmentType")),
            "date_posted": value_text(node.get("datePosted")),
            "deadline": value_text(node.get("validThrough")),
            "pay": salary_text(node),
            "description_html": node.get("description") or "",
            "source": "structured data",
        }
    return None


def company_from_url(url):
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    parts = [part for part in parsed.path.split("/") if part]
    labels = host.split(".")
    if host.endswith(("greenhouse.io", "lever.co", "ashbyhq.com")) and parts:
        slug = parts[0]
    elif labels and labels[0] in {"www", "jobs", "careers", "job-boards", "boards"} and len(labels) > 2:
        slug = labels[-2]
    elif len(labels) >= 2:
        slug = labels[-2]
    else:
        slug = host
    name = re.sub(r"[-_]+", " ", slug).strip()
    return name.title() if name else None


def company_from_title(document_title, job_title):
    if not document_title:
        return None
    match = re.search(r"\bat\s+(.+)$", document_title, re.I)
    if not match:
        return None
    company = match.group(1).strip(" |-")
    if job_title and company.lower() == job_title.lower():
        return None
    return company or None


def description_root(soup):
    selectors = (
        "[data-qa='job-description']",
        ".job__description",
        ".job-description",
        "[class*='job-description']",
        "[class*='jobDescription']",
        ".posting-page",
        "article",
        "main",
        "[role='main']",
    )
    for selector in selectors:
        node = soup.select_one(selector)
        if node and len(one_line(node.get_text(" ", strip=True))) > 200:
            return node
    return soup.body or soup


def location_from_page(soup):
    selectors = (
        ".job__location",
        ".posting-categories .location",
        ".location",
        "[data-qa='job-location']",
        "[class*='job__location']",
        "[class*='job-location']",
    )
    for selector in selectors:
        node = soup.select_one(selector)
        if not node:
            continue
        text = one_line(node.get_text(" ", strip=True))
        if 2 < len(text) < 120:
            return text
    og = meta_content(soup, "og:description")
    if og and len(og) < 80 and not re.search(r"\b(the|and|with|you|our|will)\b", og, re.I):
        return og
    return None


def is_heading_block(tag, text):
    if tag.name in {"h1", "h2", "h3", "h4", "h5", "h6"}:
        return True
    if len(text) > 80 or tag.name == "li":
        return False
    children = [
        child
        for child in tag.children
        if not (isinstance(child, NavigableString) and not str(child).strip())
    ]
    return (
        len(children) == 1
        and isinstance(children[0], Tag)
        and children[0].name in {"strong", "b"}
    )


def looks_like_label(tag, text, next_tag, next_text):
    if tag.name == "li" or next_tag is None or next_tag.name == "li":
        return False
    if not next_text or len(next_text) < 40:
        return False
    if len(text) > 50 or text.endswith((".", "!", "?")):
        return False
    if text.lower().rstrip(":") in SKIP_LABELS:
        return False
    return True


def classify_heading(text):
    lowered = text.lower().strip()
    if lowered in PAY_HINTS or any(lowered == hint for hint in PAY_HINTS):
        return "pay"
    if any(hint in lowered for hint in RESPONSIBILITY_HINTS):
        return "responsibilities"
    if any(hint in lowered for hint in QUALIFICATION_HINTS):
        return "qualifications"
    return "section"


def content_blocks(root):
    blocks = []
    for tag in root.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "p", "li"]):
        text = one_line(tag.get_text(" ", strip=True))
        if text and text.lower() not in SKIP_LABELS:
            blocks.append((tag, text))
    return blocks


def dedupe_lines(lines, limit=12):
    unique = []
    for line in lines:
        line = one_line(line).lstrip("•-* ").strip()
        if line and line not in unique:
            unique.append(line)
    return unique[:limit]


def split_sections(root):
    overview = []
    responsibilities = []
    qualifications = []
    pay_notes = []
    other = []
    current = "overview"
    pending_label = None
    blocks = content_blocks(root)

    for index, (tag, text) in enumerate(blocks):
        next_tag = blocks[index + 1][0] if index + 1 < len(blocks) else None
        next_text = blocks[index + 1][1] if next_tag is not None else ""
        # A short line ending in a colon is introducing the list that follows.
        if text.endswith(":") and next_tag is not None and next_tag.name == "li":
            continue
        heading = is_heading_block(tag, text) or looks_like_label(tag, text, next_tag, next_text)
        if heading:
            kind = classify_heading(text)
            pending_label = text.rstrip(":").strip()
            if kind == "responsibilities":
                current = "responsibilities"
                pending_label = None
            elif kind == "qualifications":
                current = "qualifications"
                pending_label = None
            elif kind == "section" and tag.name.startswith("h"):
                current = "other"
                pending_label = text.rstrip(":").strip()
            continue

        if pending_label and pending_label.lower() in PAY_HINTS:
            pay_notes.append(text)
        elif pending_label:
            other.append(f"{pending_label}: {text}")
        elif current == "responsibilities":
            responsibilities.append(text)
        elif current == "qualifications":
            qualifications.append(text)
        elif current == "overview":
            overview.append(text)
        pending_label = None

    return overview, dedupe_lines(responsibilities), dedupe_lines(qualifications), pay_notes, other


def extract_pay(text, labeled):
    snippets = []
    for line in labeled:
        snippets.append(one_line(line))
    for paragraph in re.split(r"\n+", text):
        line = one_line(paragraph)
        if not line or len(line) > 320:
            continue
        has_money = bool(re.search(r"(\$\s?\d|€\s?\d|£\s?\d)", line))
        has_pay_word = bool(
            re.search(r"\b(salary|compensation|stipend|per hour|hourly|wage|per month|per week)\b", line, re.I)
        )
        has_period = bool(re.search(r"\b(hour|week|month|year|annum)\b", line, re.I))
        if has_money and (has_pay_word or has_period):
            snippets.append(line)
    return dedupe_lines(snippets, limit=4)


def extract_duration(text):
    match = re.search(
        r"(?:at least|minimum of|up to|about)?\s*"
        r"(\d{1,2})(?:\s*(?:-|–|to)\s*(\d{1,2}))?\s*-?\s*(weeks?|months?)",
        text,
        re.I,
    )
    if not match:
        return None
    start, end, unit = match.group(1), match.group(2), match.group(3).lower()
    unit = "weeks" if unit.startswith("week") else "months"
    span = f"{start}–{end} {unit}" if end else f"{start} {unit}"
    window = text[max(0, match.start() - 24) : match.end()]
    if re.search(r"at least|minimum", window, re.I):
        return f"at least {span}"
    return span


def extract_dates(text):
    deadline = None
    start = None
    deadline_match = re.search(
        r"(?:application deadline|deadline|apply by|applications close|closing date)\s*[:\-]?\s*"
        r"([A-Z][a-z]+ \d{1,2},? \d{4}|\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|on an ongoing basis)",
        text,
        re.I,
    )
    if deadline_match:
        deadline = deadline_match.group(1)
    start_match = re.search(
        r"(?:start date|starts|starting)\s*[:\-]?\s*"
        r"([A-Z][a-z]+(?:\s+\d{1,2},?)?(?:\s+\d{4})?|(?:summer|fall|spring|winter)\s+\d{4})",
        text,
        re.I,
    )
    if start_match:
        start = start_match.group(1)
    if not start:
        season = re.search(r"\b((?:summer|fall|spring|winter)\s+20\d{2})\b", text, re.I)
        if season:
            start = season.group(1).title()
    if not start:
        flexible = re.search(
            r"((?:start|dates?).{0,40}(?:between|from)\s+[A-Z][a-z]+\s+(?:and|to|-|–)\s+[A-Z][a-z]+)",
            text,
            re.I,
        )
        if flexible:
            start = one_line(flexible.group(1))
    return start, deadline


def extract_work_model(text):
    hybrid = bool(re.search(r"\bhybrid\b", text, re.I))
    remote = bool(re.search(r"\bremote\b", text, re.I))
    office = bool(re.search(r"\b(on-site|onsite|in-office|in person|in-person)\b", text, re.I))
    if hybrid or (remote and office):
        return "Hybrid"
    if remote:
        return "Remote"
    if office:
        return "In-office"
    return None


def notable_details(other, summary, pay):
    covered = f"{summary or ''} {' '.join(pay)}"
    details = []
    for item in other:
        if ":" not in item:
            continue
        body = one_line(item.split(":", 1)[1])
        if len(body) < 20 or body[:80] in covered:
            continue
        details.append(one_line(item))
        if len(details) == 6:
            break
    return details


def summary_from(text):
    long_lines = [one_line(line) for line in text.splitlines() if len(one_line(line)) > 80]
    if not long_lines:
        return None
    summary = long_lines[0]
    if len(summary) < 280 and len(long_lines) > 1:
        summary = f"{summary} {long_lines[1]}"
    if len(summary) > 600:
        summary = summary[:597].rsplit(" ", 1)[0] + "..."
    return summary


def listing_links(soup, page_url):
    jobs = []
    seen = set()
    for link in soup.find_all("a", href=True):
        text = one_line(link.get_text(" ", strip=True))
        href = link["href"]
        if not text or len(text) < 6 or len(text) > 140:
            continue
        if not re.search(r"intern", text, re.I) and not re.search(r"intern", href, re.I):
            continue
        if href.startswith("#") or href.startswith("mailto:"):
            continue
        absolute = requests.compat.urljoin(page_url, href)
        if absolute in seen or absolute.rstrip("/") == page_url.rstrip("/"):
            continue
        seen.add(absolute)
        jobs.append({"title": text, "url": absolute})
    return jobs[:25]


def scrape_internship(url):
    url = (url or "").strip()
    if not url.startswith(("http://", "https://")):
        raise ValueError("Enter a full link, including https://")

    html, final_url = fetch_html(url)
    soup = BeautifulSoup(html, "lxml")
    structured = from_jsonld(soup)
    for tag in soup(["script", "style", "noscript", "svg", "iframe"]):
        tag.decompose()

    document_title = one_line(soup.title.get_text()) if soup.title else None
    h1 = soup.find("h1")
    title = one_line(h1.get_text(" ", strip=True)) if h1 else None
    title = title or meta_content(soup, "og:title") or document_title

    root = description_root(soup)
    _overview, responsibilities, qualifications, pay_notes, other = split_sections(root)
    if structured and structured.get("description_html") and not (responsibilities or qualifications):
        fragment = BeautifulSoup(structured["description_html"], "lxml")
        _overview, responsibilities, qualifications, pay_notes, extra = split_sections(fragment)
        other = extra or other
    description = clean(root.get_text("\n", strip=True))
    if structured and structured.get("description_html"):
        description = html_to_text(structured["description_html"]) or description

    pay = (structured or {}).get("pay") or []
    if not pay:
        pay = extract_pay(description, pay_notes)
    start, deadline = extract_dates(description)

    info = {
        "url": final_url,
        "title": (structured or {}).get("title") or title,
        "company": (structured or {}).get("company")
        or company_from_title(document_title, title)
        or company_from_url(final_url),
        "location": (structured or {}).get("location") or location_from_page(soup),
        "employment_type": (structured or {}).get("employment_type"),
        "date_posted": (structured or {}).get("date_posted"),
        "deadline": (structured or {}).get("deadline") or deadline,
        "start": start,
        "duration": extract_duration(description),
        "work_model": extract_work_model(description),
        "pay": pay,
        "summary": summary_from(description),
        "responsibilities": responsibilities,
        "qualifications": qualifications,
        "other": notable_details(other, summary_from(description), pay),
        "listings": [],
    }
    if len(description) < 500:
        info["listings"] = listing_links(soup, final_url)
    return info


def print_field(label, value):
    print(f"{label:16} {value or '—'}")


def print_internship(info):
    print("Internship")
    print("-" * 60)
    print_field("Title", info.get("title"))
    print_field("Company", info.get("company"))
    print_field("Location", info.get("location"))
    print_field("Work model", info.get("work_model"))
    print_field("Type", info.get("employment_type"))
    print_field("Duration", info.get("duration"))
    print_field("Start", info.get("start"))
    print_field("Deadline", info.get("deadline"))
    print_field("Posted", info.get("date_posted"))
    print_field("URL", info.get("url"))

    if info.get("pay"):
        print("\nCompensation")
        for item in info["pay"]:
            print(f"  • {item}")

    if info.get("summary"):
        print("\nSummary")
        print(info["summary"])

    if info.get("responsibilities"):
        print("\nResponsibilities")
        for item in info["responsibilities"]:
            print(f"  • {item}")

    if info.get("qualifications"):
        print("\nQualifications")
        for item in info["qualifications"]:
            print(f"  • {item}")

    if info.get("other"):
        print("\nOther details")
        for item in info["other"]:
            print(f"  • {item}")

    if info.get("listings"):
        print(f"\nInternship links on this page ({len(info['listings'])})")
        for job in info["listings"]:
            print(f"  • {job['title']}")
            print(f"    {job['url']}")


from auth import register_auth
from internships import register_internships

app = Flask(__name__)
CORS(app)
register_auth(app)
register_internships(app, scrape_internship)


@app.post("/scrape")
def scrape():
    body = request.get_json(silent=True) or {}
    url = body.get("url") or request.args.get("url")
    if not url:
        return jsonify({"error": "Missing url"}), 400
    try:
        info = scrape_internship(url)
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    except requests.HTTPError as error:
        status = error.response.status_code if error.response is not None else 502
        return jsonify({"error": f"The site returned {status} and the page could not be read."}), 502
    except requests.RequestException as error:
        return jsonify({"error": f"Could not reach that page: {error}"}), 502
    print_internship(info)
    return jsonify(info)


if __name__ == "__main__":
    app.run(port=5001)
