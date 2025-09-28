import requests
import csv
import time
import re
from itertools import product
from datetime import datetime
from urllib.parse import urlencode

API_KEY = '
CSE_ID = '

DATE_THRESHOLD = datetime(2025, 9, 1)

TECH_ROLES = [
    "developer", "software engineer", "backend engineer", "frontend engineer",
    "full stack developer", "mobile developer", "ios developer", "android developer",
    "qa engineer", "test engineer", "devops engineer", "data scientist", "data engineer",
    "ml engineer", "ai engineer", "prompt engineer", "llm engineer", "nlp engineer",
    "cloud engineer", "cloud architect", "solutions architect", "security engineer",
    "cybersecurity analyst", "network engineer", "database administrator",
    "systems analyst", "technical support engineer", "site reliability engineer",
    "web scraper", "scraping engineer", "automation engineer", "ui designer",
    "ux designer", "ui/ux designer", "product designer", "web designer",
    "python developer", "javascript developer", "typescript developer",
    "react developer", "node.js developer", "golang developer",
    "php developer", "ruby developer", "html/css developer"
]

JOB_PHRASES = [
    "hiring", "looking for", "open position",
    "join our team", "need", "contract role", "freelance", "remote role",
]

OUTSOURCING_KEYWORDS = [  # Keep for prompt context, not filtering in code
    "looking to outsource", "outsourcing partner", "offshore team", "nearshore team",
    "remote development team", "outsourced developers", "offshore developers",
    "remote staffing", "need development partner", "hiring agency", "development agency",
    "freelance team", "external vendor", "white label development", "external dev team",
    "need remote engineers", "augment our team", "external workforce", "staff augmentation",
    "partner with agency", "consulting partner", "outsourcing IT", "BPO partner",
    "we need remote engineers", "seeking tech partner", "scaling remotely",
    "software development partner", "remote software team", "IT outsourcing",
    "dedicated development team", "offshore software team", "hire remote developers",
    "software vendor"
]

def generate_queries():
    queries = []
    for phrase, role, keyword in product(JOB_PHRASES, TECH_ROLES, OUTSOURCING_KEYWORDS):
        query = f'site:linkedin.com/posts/ "{phrase}" "{role}" "{keyword}"'
        queries.append(query)
    return queries

def extract_date_from_snippet(snippet):
    try:
        match = re.search(r'([A-Za-z]{3,9})\s(\d{1,2}),\s(\d{4})', snippet)
        if match:
            return datetime.strptime(match.group(0), "%b %d, %Y")
    except:
        return None
    return None

def extract_author_and_company_from_link(link):
    author = "Unknown"
    company = "Unknown"

    link = link.lower()

    user_match = re.search(r'linkedin\.com/posts/([^/?#]+)', link)
    if user_match:
        author = user_match.group(1)

    company_match = re.search(r'linkedin\.com/company/([^/?#]+)/posts?', link)
    if company_match:
        company = company_match.group(1)

    return author, company

def search_employer_size(company_name):
    if not company_name or company_name == "Unknown":
        return "Unknown"

    query = f"{company_name} number of employees"
    params = {"q": query}
    url = "https://www.google.com/search?" + urlencode(params)
    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    try:
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code != 200:
            return "Unknown"

        html = res.text
        match = re.search(r'([\d,]+)\s+employees', html, re.IGNORECASE)
        if match:
            return match.group(1)
    except:
        return "Unknown"

    return "Unknown"

def mentions_asian_location(text):
    indian_locations = [
        # Indian states
        "andhra pradesh", "arunachal pradesh", "assam", "bihar", "chhattisgarh",
        "goa", "gujarat", "haryana", "himachal pradesh", "jharkhand", "karnataka",
        "kerala", "madhya pradesh", "maharashtra", "manipur", "meghalaya",
        "mizoram", "nagaland", "odisha", "punjab", "rajasthan", "sikkim",
        "tamil nadu", "telangana", "tripura", "uttar pradesh", "uttarakhand",
        "west bengal",

        # Union territories
        "andaman and nicobar islands", "chandigarh", "dadra and nagar haveli and daman and diu",
        "delhi", "lakshadweep", "puducherry", "ladakh", "jammu and kashmir",

        # Major Indian cities
        "mumbai", "delhi", "bangalore", "bengaluru", "hyderabad", "chennai",
        "kolkata", "pune", "ahmedabad", "jaipur", "lucknow", "kanpur",
        "nagpur", "indore", "thane", "bhopal", "patna", "vadodara", "agra",
        "nashik", "faridabad", "meerut", "rajkot", "varanasi", "surat",
        "gurgaon", "noida",

        # Country mention
        "india"
    ]

    text_lower = text.lower()
    return any(location in text_lower for location in indian_locations)

def search_google(query, max_results=20, seen_links=None):
    if seen_links is None:
        seen_links = set()

    all_links = []
    start = 1

    while len(all_links) < max_results:
        url = f"https://www.googleapis.com/customsearch/v1?q={query}&key={API_KEY}&cx={CSE_ID}&start={start}"
        res = requests.get(url)

        if res.status_code != 200:
            print(f"❌ Error {res.status_code}: {res.text}")
            break

        data = res.json()
        items = data.get("items", [])
        if not items:
            break

        for item in items:
            title = item.get("title")
            link = item.get("link")
            snippet = item.get("snippet", "")
            full_text = f"{title} {snippet}".lower()


            blog_url_indicators = ["/pulse/", "/articles/", "/blog/"]
            if any(indicator in link.lower() for indicator in blog_url_indicators):
                print(f"🚫 Skipped (LinkedIn Article/Blog URL): {title}")
                continue

            blog_keywords = [
                "blog", "article", "guide", "how to", "tips", "tutorial",
                "opinion", "insights", "best practices", "case study", "how", "why"
                "when"
            ]

            if any(keyword in full_text for keyword in blog_keywords):
                print(f"🚫 Skipped (Blog-like content): {title}")
                continue

            post_date = extract_date_from_snippet(snippet)

            # Skip old posts
            if not post_date or post_date < DATE_THRESHOLD:
                print(f"⏳ Skipped (no/old date): {title}")
                continue

            # Skip if Asian location (incl. India) mentioned
            if mentions_asian_location(full_text):
                print(f"🌍 Skipped (Asian location detected): {title}")
                continue

            if link in seen_links:
                print(f"🔁 Skipped (duplicate): {title}")
                continue

            author, company = extract_author_and_company_from_link(link)
            company_size = search_employer_size(company) if company != "Unknown" else "Unknown"
            seen_links.add(link)
            all_links.append((title, link, post_date, author, company, company_size))
            print(f"✅ Saved: {title}")

            if len(all_links) >= max_results:
                break

        start += 10
        time.sleep(1)

    return all_links

def save_links_to_csv(results, filename="linkedin_it_leads_filtered.csv"):
    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Title", "URL", "Date", "Author", "Company", "Company Size"])
        for title, url, post_date, author, company, company_size in results:
            date_str = post_date.strftime("%Y-%m-%d") if post_date else "Unknown"
            writer.writerow([title, url, date_str, author, company, company_size])

if __name__ == "__main__":
    all_results = []
    queries = generate_queries()
    seen_links = set()

    for i, query in enumerate(queries):
        print(f"\n🔍 {i+1}/{len(queries)} Searching: {query}")
        results = search_google(query, max_results=10, seen_links=seen_links)
        print(f"📦 {len(results)} results kept")
        all_results.extend(results)
        time.sleep(2)

    save_links_to_csv(all_results)
    print(f"\n✅ Done. {len(all_results)} total filtered posts saved to 'linkedin_it_leads_filtered.csv'")

