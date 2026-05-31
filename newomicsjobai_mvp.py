import os
import requests
import time
import feedparser
from datetime import datetime
import smtplib
import schedule
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# ═══════════════════════════════════════════════════════
#  OmicsJobAI Bot — BioInfoConnects (BIC)
#  Telegram  → Jobs ONLY
#  Website   → Jobs + Papers + Tools + Conferences
#  Newsletter → Every Monday 9AM UTC via Gmail
# ═══════════════════════════════════════════════════════

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID")
ADZUNA_APP_ID      = os.getenv("ADZUNA_APP_ID")
ADZUNA_APP_KEY     = os.getenv("ADZUNA_APP_KEY")
SUPABASE_URL       = os.getenv("SUPABASE_URL")
SUPABASE_KEY       = os.getenv("SUPABASE_KEY")
GMAIL_ADDRESS      = os.getenv("GMAIL_ADDRESS")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")

# Change v4 to v5 anytime you want a full reset of seen jobs/papers
POSTED_JOBS_FILE    = "/tmp/posted_jobs_v4.txt"
POSTED_CONTENT_FILE = "/tmp/posted_content_v4.txt"

# ── ADZUNA COUNTRIES ──────────────────────────────────
COUNTRIES = [
    "us", "ca",
    "gb", "de", "fr", "nl", "at", "be", "ch", "pl",
    "au", "sg", "in",
]

# ── JOB SEARCH KEYWORDS ───────────────────────────────
JOB_KEYWORDS = (
    "bioinformatics OR computational biology OR genomics OR "
    "proteomics OR transcriptomics OR metagenomics OR "
    "bioinformatician OR single cell OR scRNA-seq OR RNA-seq OR "
    "NGS OR epigenomics OR structural bioinformatics OR "
    "systems biology OR variant calling OR GWAS OR "
    "molecular docking OR MD simulation OR drug discovery OR "
    "cheminformatics OR machine learning biology OR "
    "deep learning genomics OR AI bioinformatics OR "
    "computational neuroscience OR multi-omics OR nanopore OR "
    "spatial transcriptomics OR postdoc bioinformatics OR "
    "staff scientist bioinformatics OR bioinformatics engineer"
)

JOB_TITLE_WORDS = [
    "scientist", "engineer", "postdoc", "post-doc", "post doc",
    "researcher", "analyst", "developer", "bioinformatician",
    "position", "vacancy", "fellow", "staff", "associate",
    "manager", "director", "technician", "specialist",
    "faculty", "professor", "lecturer", "doctoral", "phd position",
    "phd student", "internship", "hiring", "opportunity", "role"
]

PAPER_SIGNALS = [
    "doi:", "biorxiv", "arxiv", "preprint", "abstract:",
    "we report", "we present", "we show", "our study",
    "figure 1", "supplementary", "et al", "results show"
]

BLACKLIST = [
    "wet lab", "bench scientist", "pipette", "cell culture",
    "histology", "animal model", "phlebotomist", "clinical nurse",
    "surgery", "radiologist", "dentist", "pharmacy technician"
]

# ── JOB RSS FEEDS ─────────────────────────────────────
# NOTE ON LINKEDIN: LinkedIn blocks all scraping and has no
# public RSS feed. It violates their Terms of Service.
# We use Adzuna which LEGALLY aggregates LinkedIn jobs + Indeed
# + Glassdoor + 1000s of other sources via licensing agreements.
# So Adzuna already covers LinkedIn jobs legally.
JOB_RSS_FEEDS = [
    # International journals and societies
    {"name": "Nature Careers",
     "url":  "https://www.nature.com/naturecareers/rss/bioinformatics",
     "source": "Nature Careers"},
    {"name": "Science Careers (AAAS)",
     "url":  "https://jobs.sciencecareers.org/rss/jobs/?k=bioinformatics",
     "source": "Science Careers"},
    # Research institutes
    {"name": "EMBL-EBI Jobs",
     "url":  "https://www.ebi.ac.uk/about/jobs/rss",
     "source": "EMBL-EBI"},
    {"name": "EMBL Jobs",
     "url":  "https://www.embl.org/jobs/feed/",
     "source": "EMBL"},
    {"name": "Wellcome Sanger Institute",
     "url":  "https://www.sanger.ac.uk/about/careers/vacancies/feed/",
     "source": "Sanger Institute"},
    {"name": "Broad Institute",
     "url":  "https://boards.greenhouse.io/broadinstitute.rss",
     "source": "Broad Institute"},
    {"name": "Chan Zuckerberg Initiative",
     "url":  "https://boards.greenhouse.io/chanzuckerberginitiative.rss",
     "source": "CZI"},
    {"name": "NIH USA Jobs",
     "url":  "https://jobs.nih.gov/vacancies/rss/bioinformatics.xml",
     "source": "NIH"},
    # Universities
    {"name": "Oxford University Jobs",
     "url":  "https://www.jobs.ox.ac.uk/vacancy/rss?keyword=bioinformatics",
     "source": "Oxford University"},
    {"name": "Cambridge University Jobs",
     "url":  "https://www.jobs.cam.ac.uk/job/rss/?keyword=bioinformatics",
     "source": "Cambridge University"},
    # Gulf and Asia
    {"name": "KAUST Jobs (Saudi Arabia)",
     "url":  "https://careers.kaust.edu.sa/search-jobs/bioinformatics?format=rss",
     "source": "KAUST"},
    {"name": "A*STAR Singapore",
     "url":  "https://www.a-star.edu.sg/Careers/rss",
     "source": "A*STAR Singapore"},
]

# ── CONTENT RSS FEEDS ─────────────────────────────────
# Genome Biology REMOVED — replaced with Nature Communications
# and Oxford Bioinformatics journal as requested
CONTENT_RSS_FEEDS = [
    # High quality journals
    {"name": "Nature Biotechnology",
     "url":  "https://www.nature.com/nbt.rss",
     "source": "Nature Biotechnology", "type": "paper"},
    {"name": "Nature Methods",
     "url":  "https://www.nature.com/nmeth.rss",
     "source": "Nature Methods", "type": "paper"},
    {"name": "Nature Genetics",
     "url":  "https://www.nature.com/ng.rss",
     "source": "Nature Genetics", "type": "paper"},
    # NEW: Nature Communications
    {"name": "Nature Communications",
     "url":  "https://www.nature.com/ncomms.rss",
     "source": "Nature Communications", "type": "paper"},
    # NEW: Oxford Bioinformatics journal
    {"name": "Bioinformatics (Oxford OUP)",
     "url":  "https://academic.oup.com/rss/site_5504/3143.xml",
     "source": "Bioinformatics OUP", "type": "paper"},
    {"name": "PLOS Computational Biology",
     "url":  "https://journals.plos.org/ploscompbiol/feed/atom",
     "source": "PLOS Computational Biology", "type": "paper"},
    # Preprints
    {"name": "bioRxiv Bioinformatics",
     "url":  "https://connect.biorxiv.org/biorxiv_xml.php?subject=bioinformatics",
     "source": "bioRxiv", "type": "paper"},
    {"name": "bioRxiv Genomics",
     "url":  "https://connect.biorxiv.org/biorxiv_xml.php?subject=genomics",
     "source": "bioRxiv", "type": "paper"},
    # Tools
    {"name": "Bioconductor News",
     "url":  "https://bioconductor.org/rss-feeds/news.rss",
     "source": "Bioconductor", "type": "tool"},
    # Conferences
    {"name": "ISCB News",
     "url":  "https://www.iscb.org/cms_addon/rss/index.php?section=news",
     "source": "ISCB", "type": "conference"},
]

CONTENT_KEYWORDS = [
    "bioinformatics", "computational biology", "genomics", "proteomics",
    "transcriptomics", "metagenomics", "single-cell", "scRNA-seq",
    "RNA-seq", "NGS", "machine learning", "deep learning", "AI",
    "drug discovery", "molecular docking", "structural biology",
    "systems biology", "epigenomics", "multi-omics", "nanopore",
    "spatial transcriptomics", "variant calling", "GWAS", "CRISPR",
    "alphafold", "protein structure", "pathway analysis", "tool",
    "pipeline", "software", "method", "algorithm", "conference",
    "symposium", "workshop", "webinar", "genetics", "omics",
    "ageing", "aging", "mortality", "transcriptomic", "hallmarks"
]

# ── HELPER FUNCTIONS ──────────────────────────────────
def load_seen(filename):
    try:
        if os.path.exists(filename):
            age_days = (time.time() - os.path.getmtime(filename)) / 86400
            if age_days > 7:
                os.remove(filename)
                print(f"  🔄 Reset seen file (7 days old): {filename}")
        with open(filename, "r") as f:
            return set(line.strip() for line in f)
    except FileNotFoundError:
        return set()

def save_seen(item_id, filename):
    with open(filename, "a") as f:
        f.write(f"{item_id}\n")

def is_real_job(title, summary=""):
    text = (title + " " + summary).lower()
    has_job_word     = any(w in text for w in JOB_TITLE_WORDS)
    looks_like_paper = any(s in text for s in PAPER_SIGNALS)
    return has_job_word and not looks_like_paper

def is_blacklisted(title, desc=""):
    text = (title + " " + desc).lower()
    return any(w in text for w in BLACKLIST)

def is_content_relevant(title, summary=""):
    text = (title + " " + summary).lower()
    return any(kw.lower() in text for kw in CONTENT_KEYWORDS)

# ── TELEGRAM ──────────────────────────────────────────
def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        r = requests.post(url, json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "Markdown",
            "disable_web_page_preview": True
        }, timeout=10)
        if r.status_code == 200:
            print("  ✅ Telegram sent.")
        else:
            print(f"  ❌ Telegram error: {r.status_code} {r.text[:100]}")
    except Exception as e:
        print(f"  ❌ Telegram exception: {e}")

def format_job_telegram(title, company, location, link, source, country=""):
    tag = f"#{country.upper()}Jobs" if country else ""
    return (
        f"💼 *Bioinformatics Job*\n\n"
        f"📌 *{title}*\n"
        f"🏢 {company}\n"
        f"📍 {location}\n"
        f"🔗 {link}\n\n"
        f"_Via {source} · BIC_\n"
        f"#Bioinformatics #BICJobs {tag}"
    )

# ── SUPABASE ──────────────────────────────────────────
def save_job_to_supabase(title, company, location, url, source, country=""):
    if not SUPABASE_URL or not SUPABASE_KEY:
        return
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal"
    }
    try:
        r = requests.post(
            f"{SUPABASE_URL}/rest/v1/job_posts",
            headers=headers,
            json={
                "title": title, "company": company,
                "location": location, "country": country.upper(),
                "apply_url": url, "source": source,
                "posted_by": "bot", "is_active": True
            },
            timeout=10
        )
        if r.status_code in (200, 201):
            print(f"  ✅ Job saved to website DB.")
        else:
            print(f"  ⚠️  Supabase job error: {r.status_code}")
    except Exception as e:
        print(f"  ⚠️  Supabase exception: {e}")

def save_content_to_supabase(title, abstract, url, source, content_type):
    if not SUPABASE_URL or not SUPABASE_KEY:
        return
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal"
    }
    try:
        r = requests.post(
            f"{SUPABASE_URL}/rest/v1/paper_alerts",
            headers=headers,
            json={
                "title": title,
                "abstract": abstract[:1000],
                "url": url,
                "source": source,
                "journal": source,
                "posted_by": "bot",
                "is_approved": True,
                "field_tags": [content_type]
            },
            timeout=10
        )
        if r.status_code in (200, 201):
            print(f"  ✅ Content saved ({content_type}): {title[:50]}")
        elif r.status_code == 409:
            pass  # Duplicate silently skipped
        else:
            print(f"  ⚠️  Supabase content error: {r.status_code}")
    except Exception as e:
        print(f"  ⚠️  Supabase exception: {e}")

# ── FETCH JOBS ────────────────────────────────────────
def fetch_adzuna_jobs(seen):
    count = 0
    for country in COUNTRIES:
        print(f"  Checking Adzuna — {country.upper()}...")
        url = f"https://api.adzuna.com/v1/api/jobs/{country}/search/1"
        params = {
            "app_id": ADZUNA_APP_ID, "app_key": ADZUNA_APP_KEY,
            "results_per_page": 50, "what": JOB_KEYWORDS,
            "sort_by": "date", "max_days_old": 7
        }
        try:
            r = requests.get(url, params=params, timeout=15)
            if r.status_code == 200:
                for job in r.json().get("results", []):
                    jid   = f"adzuna_{job.get('id')}"
                    title = job.get('title', '')
                    desc  = job.get('description', '')
                    if jid in seen or is_blacklisted(title, desc):
                        continue
                    company  = job.get('company', {}).get('display_name', 'N/A')
                    location = job.get('location', {}).get('display_name', 'N/A')
                    link     = job.get('redirect_url', '#')
                    send_telegram(format_job_telegram(
                        title, company, location, link, "Adzuna", country))
                    save_job_to_supabase(
                        title, company, location, link, "Adzuna", country)
                    save_seen(jid, POSTED_JOBS_FILE)
                    seen.add(jid)
                    count += 1
                    time.sleep(2)
            else:
                print(f"  ⚠️  Adzuna {country.upper()}: HTTP {r.status_code}")
        except Exception as e:
            print(f"  ⚠️  Adzuna {country.upper()}: {e}")
        time.sleep(1)
    return count

def fetch_rss_jobs(seen):
    count = 0
    for feed in JOB_RSS_FEEDS:
        print(f"  Checking Jobs RSS — {feed['name']}...")
        try:
            parsed = feedparser.parse(feed['url'])
            for entry in parsed.entries:
                title   = entry.get('title', '').strip()
                link    = entry.get('link', '').strip()
                summary = entry.get('summary', '').strip()
                jid     = f"rss_job_{feed['source']}_{link}"
                if jid in seen:
                    continue
                if not is_real_job(title, summary):
                    continue
                if is_blacklisted(title, summary):
                    continue
                send_telegram(format_job_telegram(
                    title, "See link", "See link", link, feed['source']))
                save_job_to_supabase(title, "", link, feed['source'], "")
                save_seen(jid, POSTED_JOBS_FILE)
                seen.add(jid)
                count += 1
                time.sleep(2)
        except Exception as e:
            print(f"  ⚠️  RSS Jobs {feed['name']}: {e}")
        time.sleep(1)
    return count

# ── FETCH CONTENT (Website only) ──────────────────────
def fetch_website_content(seen):
    count = 0
    for feed in CONTENT_RSS_FEEDS:
        print(f"  Checking Content RSS — {feed['name']}...")
        try:
            parsed = feedparser.parse(feed['url'])
            for entry in parsed.entries:
                title   = entry.get('title', '').strip()
                link    = entry.get('link', '').strip()
                summary = entry.get('summary', '').strip()
                cid     = f"content_{feed['source']}_{link}"
                if cid in seen:
                    continue
                if not is_content_relevant(title, summary):
                    continue
                save_content_to_supabase(
                    title, summary, link, feed['source'], feed['type'])
                save_seen(cid, POSTED_CONTENT_FILE)
                seen.add(cid)
                count += 1
                time.sleep(1)
        except Exception as e:
            print(f"  ⚠️  Content RSS {feed['name']}: {e}")
        time.sleep(1)
    return count

# ── NEWSLETTER ────────────────────────────────────────
def fetch_newsletter_papers():
    papers = []
    try:
        feed = feedparser.parse(
            "https://connect.biorxiv.org/biorxiv_xml.php?subject=bioinformatics")
        for entry in feed.entries[:5]:
            title   = entry.get('title', '').strip()
            link    = entry.get('link', '').strip()
            summary = entry.get('summary', '').strip()
            if title:
                papers.append({
                    "title": title, "summary": summary[:200], "link": link})
    except Exception as e:
        print(f"Newsletter papers error: {e}")
    return papers[:3]

def fetch_newsletter_jobs():
    if not SUPABASE_URL or not SUPABASE_KEY:
        return []
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}"
    }
    try:
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/job_posts"
            f"?is_active=eq.true&order=posted_at.desc&limit=3",
            headers=headers, timeout=10)
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        print(f"Newsletter jobs error: {e}")
    return []

def fetch_newsletter_subscribers():
    if not SUPABASE_URL or not SUPABASE_KEY:
        return []
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}"
    }
    try:
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/newsletter_subscribers"
            f"?is_active=eq.true&select=email,name",
            headers=headers, timeout=10)
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        print(f"Newsletter subscribers error: {e}")
    return []

def build_newsletter_html(papers, jobs, week_str):
    papers_html = ""
    for i, p in enumerate(papers, 1):
        papers_html += f"""
        <div style="margin-bottom:1.2rem;padding:1rem;background:#f7fdfb;border-left:3px solid #1aab93;border-radius:0 8px 8px 0;">
          <div style="font-size:0.72rem;color:#1aab93;font-weight:600;text-transform:uppercase;margin-bottom:0.3rem;">Paper {i} · bioRxiv</div>
          <strong style="color:#0d1f1c;font-size:0.9rem;">{p['title'][:120]}</strong>
          <p style="color:#5a7a75;font-size:0.82rem;margin:0.4rem 0;">{p['summary'][:180]}...</p>
          <a href="{p['link']}" style="color:#1aab93;font-size:0.8rem;">Read paper →</a>
        </div>"""

    jobs_html = ""
    for j in jobs:
        jobs_html += f"""
        <div style="margin-bottom:0.75rem;padding:0.75rem 1rem;background:#f7fdfb;border-radius:8px;border:1px solid #d0e8e4;">
          <strong style="color:#0d1f1c;font-size:0.85rem;">💼 {j.get('title','')[:80]}</strong><br/>
          <span style="color:#5a7a75;font-size:0.78rem;">{j.get('company','')} · {j.get('location','')}</span><br/>
          <a href="{j.get('apply_url','#')}" style="color:#1aab93;font-size:0.78rem;">Apply →</a>
        </div>"""
    if not jobs_html:
        jobs_html = '<p style="color:#5a7a75;font-size:0.85rem;">Visit <a href="https://bioinfoconnects.netlify.app" style="color:#1aab93;">bioinfoconnects.netlify.app</a> for all jobs.</p>'

    return f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"/></head>
<body style="margin:0;padding:0;background:#f0f4f3;font-family:Arial,sans-serif;">
  <div style="background:#0d1f1c;padding:1.5rem;text-align:center;">
    <div style="display:inline-block;background:#1aab93;padding:6px 16px;border-radius:6px;color:white;font-weight:700;font-size:1.1rem;letter-spacing:2px;">BIC</div>
    <h1 style="color:white;font-size:1.2rem;margin:0.5rem 0;">Weekly Bioinformatics Digest</h1>
    <p style="color:#7aada7;font-size:0.82rem;margin:0;">{week_str}</p>
  </div>
  <div style="max-width:580px;margin:0 auto;padding:1.5rem 1rem;">
    <h2 style="color:#0d1f1c;font-size:0.95rem;text-transform:uppercase;letter-spacing:1px;">🧬 Top Papers This Week</h2>
    {papers_html}
    <h2 style="color:#0d1f1c;font-size:0.95rem;text-transform:uppercase;letter-spacing:1px;margin-top:1.5rem;">💼 Selected Jobs</h2>
    {jobs_html}
    <div style="background:#0d1f1c;border-radius:10px;padding:1.25rem;text-align:center;margin:1.5rem 0;">
      <a href="https://bioinfoconnects.netlify.app"
         style="background:#1aab93;color:white;padding:11px 26px;border-radius:7px;text-decoration:none;font-weight:600;font-size:0.88rem;">
        Visit BioInfoConnects →
      </a>
    </div>
    <p style="color:#7aada7;font-size:0.72rem;text-align:center;">
      © 2026 BioInfoConnects (BIC) · Founded by MSA<br/>
      Albert Einstein College of Medicine, New York, USA<br/>
      You received this because you subscribed at bioinfoconnects.netlify.app
    </p>
  </div>
</body></html>"""

def send_weekly_newsletter():
    week_str = datetime.now().strftime("Week of %B %d, %Y")
    print(f"\n{'='*50}")
    print(f"BIC Weekly Newsletter — {week_str}")
    print(f"{'='*50}")

    if not GMAIL_ADDRESS or not GMAIL_APP_PASSWORD:
        print("Gmail credentials missing — skipping newsletter.")
        return

    papers      = fetch_newsletter_papers()
    jobs        = fetch_newsletter_jobs()
    subscribers = fetch_newsletter_subscribers()
    print(f"Papers: {len(papers)} | Jobs: {len(jobs)} | Subscribers: {len(subscribers)}")

    if not subscribers:
        print("No subscribers yet — skipping send.")
        return

    html = build_newsletter_html(papers, jobs, week_str)
    sent = 0

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
            for sub in subscribers:
                try:
                    msg = MIMEMultipart("alternative")
                    msg["Subject"] = f"BIC Weekly Digest — {week_str}"
                    msg["From"]    = f"BioInfoConnects BIC <{GMAIL_ADDRESS}>"
                    msg["To"]      = sub['email']
                    msg.attach(MIMEText(html, "html"))
                    server.sendmail(GMAIL_ADDRESS, sub['email'], msg.as_string())
                    print(f"  ✅ Sent to {sub['email']}")
                    sent += 1
                    time.sleep(1)
                except Exception as e:
                    print(f"  ❌ Failed {sub['email']}: {e}")
    except Exception as e:
        print(f"  ❌ Gmail error: {e}")

    print(f"Newsletter done. Sent: {sent}/{len(subscribers)}")

    try:
        paper_lines = "\n".join([f"📄 {p['title'][:60]}..." for p in papers])
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": (
                    f"📰 *BIC Weekly Digest — {week_str}*\n\n"
                    f"🧬 *Top Papers:*\n{paper_lines}\n\n"
                    f"🌐 Full digest: bioinfoconnects.netlify.app\n"
                    f"#BIC #Bioinformatics #WeeklyDigest"
                ),
                "parse_mode": "Markdown"
            },
            timeout=10
        )
        print("  ✅ Digest posted to Telegram.")
    except Exception as e:
        print(f"  ❌ Telegram digest error: {e}")

# Schedule newsletter every Monday 9AM UTC
schedule.every().monday.at("09:00").do(send_weekly_newsletter)

# ── MAIN LOOP ─────────────────────────────────────────
def main():
    print("=" * 55)
    print("  OmicsJobAI Bot — BioInfoConnects (BIC)")
    print("  Telegram = Jobs ONLY")
    print("  Website  = Jobs + Papers + Tools + Conferences")
    print("  Newsletter = Every Monday 9AM UTC")
    print("=" * 55)

    while True:
        try:
            print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Starting cycle...")

            seen_jobs    = load_seen(POSTED_JOBS_FILE)
            seen_content = load_seen(POSTED_CONTENT_FILE)

            print("\n── JOBS (Telegram + Website) ──")
            j1 = fetch_adzuna_jobs(seen_jobs)
            j2 = fetch_rss_jobs(seen_jobs)
            print(f"  Total new jobs: {j1 + j2}")

            print("\n── CONTENT (Website only) ──")
            c1 = fetch_website_content(seen_content)
            print(f"  Total new content items: {c1}")

            print("\n── NEWSLETTER CHECK ──")
            schedule.run_pending()

            print(f"\n  ✅ Cycle complete. Sleeping 1 hour...")
            time.sleep(3600)

        except Exception as e:
            print(f"❌ Critical error: {e}")
            time.sleep(300)

if __name__ == "__main__":
    main()
