import pandas as pd
import requests
import re
import time
import os
import glob
from concurrent.futures import ThreadPoolExecutor, as_completed

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

GITHUB_TOKEN = os.getenv("GITHUB_ACCESS_KEY")

if not GITHUB_TOKEN:
    raise ValueError("GitHub token not found! Please ensure it is set in the ../.env.local file.")

CENTRAL_REPOSITORY = os.getenv("GITHUB_REPOSITORY", "anonymous/repository")

HEADERS = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json"
}

MAX_WORKERS = 10  
TIMEOUT_SECS = 15

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

def get_latest_execution_folder(base_path="../executions"):
    if not os.path.exists(base_path):
        raise FileNotFoundError(f"Base directory not found: {base_path}")
        
    folders = [os.path.join(base_path, d) for d in os.listdir(base_path) if os.path.isdir(os.path.join(base_path, d))]
    if not folders:
        raise FileNotFoundError(f"Execution folder not found in {base_path}")
        
    return max(folders, key=os.path.getmtime)

EXECUTION_DIR = get_latest_execution_folder()
BUILDS_FILE = os.path.join(EXECUTION_DIR, "raw_github_builds.csv")
OUTPUT_FILE = os.path.join(EXECUTION_DIR, "why_build_failed.csv")

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

def process_build(row):
    run_id = row['run_id']
    branch = str(row['head_branch'])
    
    match = re.search(r"mining-framework-analysis_(?P<project>.+?)_[a-f0-9]{40}_merge\.", branch)
    original_project = match.group('project') if match else "Unknown"
        
    url_jobs = f"https://api.github.com/repos/{CENTRAL_REPOSITORY}/actions/runs/{run_id}/jobs"
    
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
            time.sleep(10)
            return process_build(row)
            
    except requests.exceptions.Timeout:
        return {
            'run_id': run_id, 
            'project_original': original_project, 
            'branch': branch, 
            'fail_reason': "Log Unavailable",
            'error_message': "GitHub took too long to respond."
        }
    except requests.exceptions.RequestException as e:
        return {
            'run_id': run_id, 
            'project_original': original_project, 
            'branch': branch, 
            'fail_reason': "Log Unavailable",
            'error_message': str(e)
        }
        
    return {
        'run_id': run_id, 
        'project_original': original_project, 
        'branch': branch, 
        'fail_reason': "Log Unavailable",
        'error_message': ""
    }

print(f"Using data from: {EXECUTION_DIR}")
print(f"Loading failed builds from repository {CENTRAL_REPOSITORY}...")

if not os.path.exists(BUILDS_FILE):
    raise FileNotFoundError(f"File {BUILDS_FILE} not found.")

df_builds = pd.read_csv(BUILDS_FILE)
df_failures = df_builds[
    (df_builds['conclusion'] == 'failure') & 
    (df_builds['head_branch'].str.contains('_merge.'))
].copy()

total_failures = len(df_failures)
print(f"Starting parallel log extraction for {total_failures} broken builds...\n")

classification_results = []
completed = 0

with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
    futures = [executor.submit(process_build, row) for _, row in df_failures.iterrows()]
    
    for future in as_completed(futures):
        completed += 1
        result = future.result()
        
        if result:
            classification_results.append(result)
            print(f"[{completed}/{total_failures}] {result['project_original']} -> {result['fail_reason']}")

df_reasons = pd.DataFrame(classification_results)
if not df_reasons.empty:
    df_reasons.to_csv(OUTPUT_FILE, index=False)
    print(f"\nProcess complete. Saved to '{OUTPUT_FILE}'.")
    print("\nReasons summary:")
    print(df_reasons['fail_reason'].value_counts())