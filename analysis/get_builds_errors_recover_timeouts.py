import pandas as pd
import requests
import re
import time
import os
import glob
from concurrent.futures import ThreadPoolExecutor, as_completed

# Resolve the absolute path to the root directory's .env.local
current_dir = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(current_dir, '..', '.env.local')

if os.path.exists(env_path):
    with open(env_path, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip() and not line.startswith('#'):
                try:
                    key, value = line.strip().split('=', 1)
                    os.environ[key.strip()] = value.strip()
                except ValueError:
                    continue

# Configuration
GITHUB_TOKEN = os.getenv("GITHUB_ACCESS_KEY")
if not GITHUB_TOKEN:
    raise ValueError("GitHub token not found! Please ensure it is set in the ../.env.local file.")

CENTRAL_REPOSITORY = os.getenv("GITHUB_REPOSITORY", "anonymous/repository")

HEADERS = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json"
}

def get_latest_execution_folder(base_path="../executions"):
    if not os.path.exists(base_path):
        raise FileNotFoundError(f"Base directory not found: {base_path}")
    folders = [os.path.join(base_path, d) for d in os.listdir(base_path) if os.path.isdir(os.path.join(base_path, d))]
    if not folders:
        raise FileNotFoundError(f"Execution folder not found in {base_path}")
    return max(folders, key=os.path.getmtime)

EXECUTION_DIR = get_latest_execution_folder()
REASONS_FILE = os.path.join(EXECUTION_DIR, "why_build_failed.csv")

MAX_WORKERS = 8 
TIMEOUT_SECS = 60 
RETRIES = 3 

KEYWORDS_DEPENDENCY = [
    "could not resolve dependencies", "failed to collect dependencies", 
    "npm err! network", "npm err! code e404", 
    "modulenotfounderror: no module named", 
    "connection timed out", "failed to download", 
    "unresolved import", "module not found"
]

KEYWORDS_TESTS = [
    "tests run:", "testsuites", "failing tests:", "test failed"
]

def classify_log_with_snippet(log_text):
    log_text_lower = log_text.lower()
    lines = log_text.split('\n')
    
    def get_context(index, num_lines=20):
        start = max(0, index - num_lines)
        end = min(len(lines), index + num_lines + 1)
        return "\n".join(lines[start:end]).strip()

    for kw in KEYWORDS_DEPENDENCY:
        if kw in log_text_lower:
            for i, line in enumerate(lines):
                if kw in line.lower():
                    return "Dependency/Environment Error", get_context(i)
            
    if "compilation error" not in log_text_lower and "build success" in log_text_lower:
        for kw in KEYWORDS_TESTS:
            if kw in log_text_lower:
                for i, line in enumerate(lines):
                    if kw in line.lower():
                        return "Semantic Failure (Tests)", get_context(i)
    
    for i, line in enumerate(lines):
        if "error:" in line.lower() or "compilation error" in line.lower() or "syntaxerror" in line.lower():
            return "Compilation/Syntax Error", get_context(i)
            
    final_snippet = "\n".join(lines[-50:]).strip()
    return "Compilation/Syntax Error (Fallback)", final_snippet

def process_recovery(row):
    run_id = row['run_id']
    branch = row['branch']
    original_project = row['project_original']
    
    url_jobs = f"https://api.github.com/repos/{CENTRAL_REPOSITORY}/actions/runs/{run_id}/jobs"
    
    for attempt in range(1, RETRIES + 1):
        try:
            res_jobs = requests.get(url_jobs, headers=HEADERS, timeout=TIMEOUT_SECS)
            
            if res_jobs.status_code == 200:
                jobs = res_jobs.json().get('jobs', [])
                log_text = ""
                
                for job in jobs:
                    if job['conclusion'] == 'failure':
                        job_id = job['id']
                        url_log = f"https://api.github.com/repos/{CENTRAL_REPOSITORY}/actions/jobs/{job_id}/logs"
                        
                        res_log = requests.get(url_log, headers=HEADERS, timeout=TIMEOUT_SECS)
                        if res_log.status_code == 200:
                            log_text += res_log.text
                
                if log_text:
                    reason, snippet = classify_log_with_snippet(log_text)
                    return {
                        'run_id': run_id, 
                        'project_original': original_project, 
                        'branch': branch, 
                        'fail_reason': reason, 
                        'error_message': snippet
                    }
                    
            elif res_jobs.status_code in [403, 429]:
                time.sleep(15) 
                continue
                
        except requests.exceptions.Timeout:
            print(f"Timeout on attempt {attempt}/{RETRIES} for {original_project}...")
            time.sleep(5)
            continue
        except requests.exceptions.RequestException:
            time.sleep(5)
            continue

    return {
        'run_id': run_id, 
        'project_original': original_project, 
        'branch': branch, 
        'fail_reason': "Log Unavailable (Final)", 
        'error_message': "Failed after multiple attempts."
    }

# Main Execution
print(f"Loading previous results from: {REASONS_FILE}")
if not os.path.exists(REASONS_FILE):
    raise FileNotFoundError(f"File {REASONS_FILE} not found.")

df_current = pd.read_csv(REASONS_FILE)

# Separate successful classifications from network-related failures
mask_network_failures = df_current['fail_reason'].str.contains("Unavailable")
df_success = df_current[~mask_network_failures].copy()
df_retry = df_current[mask_network_failures].copy()

total_to_recover = len(df_retry)
print(f"Attempting to recover {total_to_recover} lost logs with 60s timeout...\n")

recovered_results = []
completed = 0

with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
    futures = [executor.submit(process_recovery, row) for _, row in df_retry.iterrows()]
    
    for future in as_completed(futures):
        completed += 1
        result = future.result()
        recovered_results.append(result)
        print(f"[{completed}/{total_to_recover}] {result['project_original']} -> {result['fail_reason']}")

df_new = pd.DataFrame(recovered_results)
df_final = pd.concat([df_success, df_new], ignore_index=True)

df_final.to_csv(REASONS_FILE, index=False)
print(f"\nRecovery Complete. File '{REASONS_FILE}' updated.")
print("\nUpdated Reasons Summary:")
print(df_final['fail_reason'].value_counts())