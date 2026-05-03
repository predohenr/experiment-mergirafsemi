import requests
import pandas as pd
import time
import math
import os
import glob

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

GITHUB_TOKEN = os.getenv("GITHUB_ACCESS_KEY")

if not GITHUB_TOKEN:
    raise ValueError("GitHub token not found! Please ensure it is set in the ../.env.local file.")

CENTRAL_REPOSITORY = os.getenv("GITHUB_REPOSITORY", "anonymous/repository")

HEADERS = {
    'Authorization': f'token {GITHUB_TOKEN}',
    'Accept': 'application/vnd.github.v3+json'
}

def get_latest_execution_folder(base_path="../executions"):
    if not os.path.exists(base_path):
        raise FileNotFoundError(f"Base directory not found: {base_path}")
        
    folders = [os.path.join(base_path, d) for d in os.listdir(base_path) if os.path.isdir(os.path.join(base_path, d))]
    if not folders:
        raise FileNotFoundError(f"Execution folder not found in {base_path}")
        
    return max(folders, key=os.path.getmtime)

def download_all_workflow_runs():
    EXECUTION_DIR = get_latest_execution_folder()
    print(f"Using data from: {EXECUTION_DIR}")
    
    print(f"Initiating connection to {CENTRAL_REPOSITORY}...")
    
    url_init = f"https://api.github.com/repos/{CENTRAL_REPOSITORY}/actions/runs?per_page=1&page=1"
    resp_init = requests.get(url_init, headers=HEADERS)
    
    if resp_init.status_code != 200:
        print(f"API Error: {resp_init.status_code} - {resp_init.text}")
        return
        
    total_count = resp_init.json().get('total_count', 0)
    total_pages = math.ceil(total_count / 100)
    
    print(f"Found {total_count} executions in the repository history.")
    print(f"This will result in exactly {total_pages} download batches.\n")
    print("=" * 50)
    
    all_runs = []
    
    for page in range(1, total_pages + 1):
        url = f"https://api.github.com/repos/{CENTRAL_REPOSITORY}/actions/runs?per_page=100&page={page}"
        response = requests.get(url, headers=HEADERS)
        
        if response.status_code != 200:
            print(f"[Batch {page:02d}/{total_pages:02d}] ERROR during request: {response.status_code}")
            break
            
        data = response.json()
        runs = data.get('workflow_runs', [])
        
        if not runs:
            print(f"[Batch {page:02d}/{total_pages:02d}] Empty batch. End of records.")
            break
            
        for run in runs:
            all_runs.append({
                'run_id': run['id'],
                'head_branch': run['head_branch'],
                'head_sha': run['head_sha'],
                'status': run['status'],
                'conclusion': run['conclusion'],
                'created_at': run['created_at'],
                'updated_at': run['updated_at'],
                'workflow_id': run['workflow_id']
            })
            
        print(f"[Batch {page:02d}/{total_pages:02d}] Complete! ({len(runs)} records extracted)")
        time.sleep(0.5) 
        
    print("=" * 50)
    print("Processing data and removing duplicate branches (keeping the most recent build)...")
    
    df_raw = pd.DataFrame(all_runs)
    df_raw = df_raw.drop_duplicates(subset=['head_branch'], keep='first')
    
    output_file = os.path.join(EXECUTION_DIR, 'raw_github_builds.csv')
    df_raw.to_csv(output_file, index=False)
    print(f"Extraction 100% complete. {len(df_raw)} unique branches successfully saved to '{output_file}'.")

if __name__ == '__main__':
    download_all_workflow_runs()