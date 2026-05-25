import os
import requests
import time
import json
import feedparser
from datetime import datetime

# ─────────────────────────────────────────────
# OmicsJobAI Bot — BioInfoConnects (BIC)
# Legal sources only:
#   - Adzuna API (licensed job aggregator)
#   - ISCB Jobs RSS (public feed, free to read)
#   - Nature Careers RSS (public feed)
#   - New Scientist Jobs RSS (public feed)
# We do NOT scrape LinkedIn, Indeed, Glassdoor
# directly — this would violate their ToS.
# Adzuna legally syndicates from those platforms.
# ─────────────────────────────────────────────

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID")
ADZUNA_APP_ID      = os.getenv("ADZUNA_APP_ID")
ADZUNA_APP_KEY     = os.getenv("ADZUNA_APP_KEY")

POSTED_JOBS_FILE = "posted_jobs.txt"

# ── EXPANDED COUNTRIES ────────────────────────
# Organised by region for clarity
# Adzuna officially supported countries only
# HTTP 404 = country not in Adzuna database
# UAE, China, Taiwan, South Korea, Singapore jobs
# appear via IN (India) and GB (global) results
COUNTRIES = [
    # North America
    "us", "ca",
    # Europe (Adzuna verified)
    "gb", "de", "fr", "nl", "at", "be", "ch", "pl",
    # Asia Pacific (Adzuna verified)
    "au", "sg", "in",
]

# Note: China, Taiwan, UAE, South Korea are not
# in Adzuna's supported country list. Jobs from
# those regions appear under global/sg/in results.

# ── EXPANDED KEYWORDS ────────────────────────
# Adzuna supports OR logic in the "what" field
KEYWORDS = (
    "bioinformatics OR computational biology OR genomics OR proteomics OR "
    "transcriptomics OR metagenomics OR bioinformatician OR omics OR "
    "single cell OR scRNA-seq OR RNA-seq OR NGS OR next generation sequencing OR "
    "epigenomics OR structural bioinformatics OR systems biology OR "
    "computational genomics OR genome assembly OR variant calling OR GWAS OR "
    "phylogenomics OR metabolomics OR spatial transcriptomics OR "
    "multi-omics OR pangenomics OR long read sequencing OR nanopore OR "
    "computational chemistry OR molecular docking OR MD simulation OR "
    "molecular dynamics OR drug discovery computational OR "
    "cheminformatics OR QSAR OR virtual screening OR "
    "machine learning biology OR deep learning genomics OR "
    "AI drug discovery OR artificial intelligence bioinformatics OR "
    "computational neuroscience OR genetics computational OR "
    "postdoc bioinformatics OR staff scientist bioinformatics OR "
    "research scientist computational OR senior scientist bioinformatics OR "
    "bioinformatics engineer OR data scientist genomics OR "
    "principal investigator bioinformatics OR research associate computational"
)

# ── BLACKLIST (wet-lab / non-computational) ──
BLACKLIST = [
    "wet lab", "bench scientist", "pipette", "cell culture",
    "histology", "animal model", "mouse model", "rat model",
    "phlebotomist", "clinical nurse", "surgery", "radiologist",
    "dentist", "pharmacy technician"
]

# ── PUBLIC RSS JOB FEEDS (legal to read) ─────
# Public RSS feeds — verified working URLs
# These are free public feeds, legal to read
RSS_FEEDS = [
    {
        "name": "Nature Careers — Bioinformatics",
        "url": "https://www.nature.com/naturecareers/rss/bioinformatics",
        "source": "Nature Careers"
    },
    {
        "name": "EBI Jobs",
        "url": "https://www.ebi.ac.uk/about/jobs/rss",
        "source": "EMBL-EBI"
    },
    {
        "name": "EMBL Jobs",
        "url": "https://www.embl.org/jobs/feed/",
        "source": "EMBL"
    },
    {
        "name": "bioRxiv — Bioinformatics",
        "url": "https://connect.biorxiv.org/biorxiv_xml.php?subject=bioinformatics",
        "source": "bioRxiv"
    },
]

# ── KEYWORDS FOR RSS FILTER ──────────────────
RSS_KEYWORDS = [
    "bioinformatics", "computational biology", "genomics", "proteomics",
    "transcriptomics", "metagenomics", "single-cell", "RNA-seq", "NGS",
    "machine learning", "deep learning", "AI", "drug discovery",
    "molecular docking", "MD simulation", "molecular dynamics",
    "cheminformatics", "structural biology", "systems biology",
    "epigenomics", "multi-omics", "computational", "omics",
    "genetics", "variant calling", "GWAS", "nanopore",
]

def load_posted_jobs():
    try:
        with open(POSTED_JOBS_FILE, "r") as f:
            return set(line.strip() for line in f)
    except FileNotFoundError:
        return set()

def save_posted_job(job_id):
    with open(POSTED_JOBS_FILE, "a") as f:
        f.write(f"{job_id}\n")

def is_relevant(title, description=""):
    text = (title + " " + description).lower()
    if any(word in text for word in BLACKLIST):
        return False
    return True

def send_to_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    }
    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            print("✅ Telegram message sent.")
        else:
            print(f"❌ Telegram error: {response.status_code} {response.text}")
    except Exception as e:
        print(f"❌ Telegram exception: {e}")

def format_adzuna_message(job, country):
    title    = job.get('title', 'N/A')
    company  = job.get('company', {}).get('display_name', 'N/A')
    location = job.get('location', {}).get('display_name', 'N/A')
    link     = job.get('redirect_url', '#')
    salary   = job.get('salary_min')
    salary_text = f"💰 *Salary:* ${int(salary):,}/year\n" if salary else ""
    country_upper = country.upper()

    return (
        f"🔬 *New Bioinformatics Job — {country_upper}*\n\n"
        f"📌 *{title}*\n"
        f"🏢 *Company:* {company}\n"
        f"📍 *Location:* {location}\n"
        f"{salary_text}"
        f"🔗 *Apply:* {link}\n\n"
        f"_Via Adzuna · BioInfoConnects_\n"
        f"#Bioinformatics #BIC #OmicsJobs #{country_upper}Jobs"
    )

def format_rss_message(entry, source_name):
    title    = entry.get('title', 'N/A').strip()
    link     = entry.get('link', '#').strip()
    summary  = entry.get('summary', '')[:200].strip()
    summary_text = f"📝 _{summary}..._\n" if summary else ""

    return (
        f"💼 *New Job — {source_name}*\n\n"
        f"📌 *{title}*\n"
        f"{summary_text}"
        f"🔗 *Apply:* {link}\n\n"
        f"_Via {source_name} · BioInfoConnects_\n"
        f"#Bioinformatics #BIC #OmicsJobs"
    )

def fetch_adzuna_jobs(posted_jobs):
    new_jobs = []
    for country in COUNTRIES:
        print(f"  Checking Adzuna — {country.upper()}...")
        url = f"https://api.adzuna.com/v1/api/jobs/{country}/search/1"
        params = {
            "app_id":          ADZUNA_APP_ID,
            "app_key":         ADZUNA_APP_KEY,
            "results_per_page": 50,
            "what":            KEYWORDS,
            "sort_by":         "date",
            "max_days_old":    7,   # Search last 7 days — catches maximum jobs
        }
        try:
            r = requests.get(url, params=params, timeout=15)
            if r.status_code == 200:
                results = r.json().get("results", [])
                for job in results:
                    job_id = f"adzuna_{job.get('id')}"
                    title  = job.get('title', '')
                    desc   = job.get('description', '')
                    if job_id not in posted_jobs and is_relevant(title, desc):
                        new_jobs.append((job_id, format_adzuna_message(job, country)))
                        posted_jobs.add(job_id)
            else:
                print(f"  ⚠️  Adzuna {country.upper()}: HTTP {r.status_code}")
        except Exception as e:
            print(f"  ⚠️  Adzuna {country.upper()} error: {e}")
        time.sleep(1)
    return new_jobs

def fetch_rss_jobs(posted_jobs):
    new_jobs = []
    for feed in RSS_FEEDS:
        print(f"  Checking RSS — {feed['name']}...")
        try:
            parsed = feedparser.parse(feed['url'])
            for entry in parsed.entries:
                title   = entry.get('title', '')
                link    = entry.get('link', '')
                summary = entry.get('summary', '')
                job_id  = f"rss_{feed['source']}_{link}"

                # Check keyword relevance
                text = (title + " " + summary).lower()
                if not any(kw.lower() in text for kw in RSS_KEYWORDS):
                    continue

                if job_id not in posted_jobs and is_relevant(title, summary):
                    new_jobs.append((job_id, format_rss_message(entry, feed['name'])))
                    posted_jobs.add(job_id)
        except Exception as e:
            print(f"  ⚠️  RSS {feed['name']} error: {e}")
        time.sleep(1)
    return new_jobs

def main():
    print("=" * 55)
    print("  OmicsJobAI Bot — BioInfoConnects (BIC)")
    print("  Legal sources: Adzuna API + Public RSS feeds")
    print("=" * 55)

    while True:
        try:
            print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Starting job search...")
            posted_jobs = load_posted_jobs()

            # Fetch from Adzuna (licensed aggregator)
            adzuna_jobs = fetch_adzuna_jobs(posted_jobs)
            print(f"  Adzuna: {len(adzuna_jobs)} new jobs found")

            # Fetch from public RSS feeds
            rss_jobs = fetch_rss_jobs(posted_jobs)
            print(f"  RSS feeds: {len(rss_jobs)} new jobs found")

            all_new_jobs = adzuna_jobs + rss_jobs
            print(f"  Total new jobs this cycle: {len(all_new_jobs)}")

            for job_id, message in all_new_jobs:
                send_to_telegram(message)
                save_posted_job(job_id)
                time.sleep(2)

            print(f"  Done. Sleeping 3600 seconds (1 hour)...")
            time.sleep(3600)

        except Exception as e:
            print(f"❌ Critical error: {e}")
            print("  Sleeping 300 seconds before retry...")
            time.sleep(300)

if __name__ == "__main__":
    main()
