import os
import time
import requests
from dotenv import load_dotenv
# from openai import OpenAI  # COMMENT KAR DIYA

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")  # YE RAILWAY ME ADD KARNA PADEGA

ADZUNA_ID = os.getenv("ADZUNA_APP_ID")
ADZUNA_KEY = os.getenv("ADZUNA_APP_KEY")

# client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))  # COMMENT

SENT_JOBS_FILE = "sent_jobs.txt"

def get_sent_jobs():
    try:
        with open(SENT_JOBS_FILE, "r") as f:
            return set(f.read().splitlines())
    except FileNotFoundError:
        return set()

def save_sent_job(job_id):
    with open(SENT_JOBS_FILE, "a") as f:
        f.write(f"{job_id}\n")

def fetch_adzuna_jobs():
    url = "https://api.adzuna.com/v1/api/jobs/gb/search/1"
    params = {
        "app_id": ADZUNA_ID,
        "app_key": ADZUNA_KEY,
        "results_per_page": 20,
        "what": "bioinformatics genomics computational biology",
        "where": "EUROPE",
        "content-type": "application/json",
    }
    r = requests.get(url, params=params)
    r.raise_for_status()
    return r.json().get("results", [])

def summarize_job(title, desc, company, location):
    # OpenAI bypass - direct return
    return f"🧬 {title} at {company}, {location}"

def send_telegram_message(msg):
    if not CHAT_ID:
        print("TELEGRAM_CHAT_ID missing. Skipping send.")
        return
        
    telegram_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    response = requests.post(
        telegram_url,
        data={
            "chat_id": CHAT_ID,
            "text": msg,
            "disable_web_page_preview": True,
        },
    )
    response.raise_for_status()

def send_job(job):
    job_id = str(job["id"])
    title = job.get("title", "No title")
    company = job.get("company", {}).get("display_name", "Unknown company")
    location = job.get("location", {}).get("display_name", "Unknown location")
    url = job.get("redirect_url", "")
    desc = job.get("description", "")
    
    summary = summarize_job(title, desc, company, location)
    
    msg = f"""{summary}

📍 {location}
🏢 {company}
🔗 Apply: {url}

#Bioinformatics #Genomics #Jobs
"""
    
    send_telegram_message(msg)
    save_sent_job(job_id)
    print(f"Sent: {title}")

def main():
    print("Starting OmicsJobAI MVP...")
    sent_jobs = get_sent_jobs()
    jobs = fetch_adzuna_jobs()
    new_jobs = [j for j in jobs if str(j["id"]) not in sent_jobs]
    print(f"Found {len(new_jobs)} new jobs.")
    
    for job in new_jobs[:5]:
        send_job(job)
        time.sleep(2)
    
    print("Sleeping for 3600 seconds.")

if __name__ == "__main__":
    while True:
        main()
        time.sleep(3600)
