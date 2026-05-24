import os
import requests
import time
import json
from datetime import datetime

# --- Configuration ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
ADZUNA_APP_ID = os.getenv("ADZUNA_APP_ID")
ADZUNA_APP_KEY = os.getenv("ADZUNA_APP_KEY")

# File to track posted jobs to prevent duplicates
POSTED_JOBS_FILE = "posted_jobs.txt"

# --- Search Parameters ---
COUNTRIES = ["gb", "us", "de", "ca", "au", "in", "sg", "nl"]  # UK, USA, Germany, Canada, Australia, India, Singapore, Netherlands
KEYWORDS = "bioinformatics OR computational biology OR genomics OR proteomics OR transcriptomics OR bioinformatician OR postdoc bioinformatics OR research assistant bioinformatics OR staff scientist OR senior scientist bioinformatics OR omics OR NGS OR single cell"

# Blacklist to filter out wet-lab jobs
BLACKLIST = ["wet lab", "experimental", "bench", "pipette", "molecular biology", "cell culture"]

def load_posted_jobs():
    """Load previously posted job IDs from file."""
    try:
        with open(POSTED_JOBS_FILE, "r") as f:
            return set(line.strip() for line in f)
    except FileNotFoundError:
        return set()

def save_posted_job(job_id):
    """Save a job ID to the posted jobs file."""
    with open(POSTED_JOBS_FILE, "a") as f:
        f.write(f"{job_id}\n")

def is_relevant(job):
    """Check if job is relevant to computational work using blacklist."""
    text = (job.get('title', '') + ' ' + job.get('description', '')).lower()
    if any(word in text for word in BLACKLIST):
        return False
    return True

def send_to_telegram(message):
    """Send formatted message to Telegram channel."""
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
            print("Message sent to Telegram successfully.")
        else:
            print(f"Failed to send to Telegram: {response.status_code} {response.text}")
    except Exception as e:
        print(f"Error sending to Telegram: {e}")

def fetch_jobs():
    """Fetch jobs from Adzuna across all specified countries."""
    all_jobs = []
    posted_jobs = load_posted_jobs()
    
    for country in COUNTRIES:
        print(f"Checking {country.upper()}...")
        url = f"https://api.adzuna.com/v1/api/jobs/{country}/search/1"
        params = {
            "app_id": ADZUNA_APP_ID,
            "app_key": ADZUNA_APP_KEY,
            "results_per_page": 10,
            "what": KEYWORDS,
            "sort_by": "date",
            "max_days_old": 1
        }
        try:
            response = requests.get(url, params=params, timeout=15)
            if response.status_code == 200:
                data = response.json()
                results = data.get("results", [])
                for job in results:
                    job_id = str(job.get("id"))
                    if job_id not in posted_jobs and is_relevant(job):
                        all_jobs.append(job)
                        posted_jobs.add(job_id)  # Mark as seen for this run
            else:
                print(f"Adzuna API error for {country}: {response.status_code}")
        except Exception as e:
            print(f"Error fetching from {country}: {e}")
        
        time.sleep(1)  # Rate limit: 1 second between country requests
    
    return all_jobs

def format_job_message(job):
    """Format job data into Telegram message."""
    title = job.get('title', 'N/A')
    company = job.get('company', {}).get('display_name', 'N/A')
    location = job.get('location', {}).get('display_name', 'N/A')
    link = job.get('redirect_url', '#')
    salary = job.get('salary_min')
    salary_text = f"*Salary:* ${int(salary):,}/year\n" if salary else ""
    
    message = f"""🔬 *New Bioinformatics Job*

*Title:* {title}
*Company:* {company}
*Location:* {location}
{salary_text}*Link:* {link}"""
    return message

def main():
    """Main execution loop."""
    print("Starting OmicsJobAI MVP...")
    
    while True:
        try:
            new_jobs = fetch_jobs()
            print(f"Found {len(new_jobs)} new relevant jobs.")
            
            for job in new_jobs:
                message = format_job_message(job)
                send_to_telegram(message)
                save_posted_job(str(job.get("id")))
                time.sleep(2)  # Avoid Telegram rate limits
            
            print("Sleeping for 3600 seconds.")
            time.sleep(3600)  # 1 hour
            
        except Exception as e:
            print(f"Critical error in main loop: {e}")
            print("Sleeping for 300 seconds before retry.")
            time.sleep(300)  # Wait 5 min on error

if __name__ == "__main__":
    main()
