import pandas as pd
import requests
import os
import time
import re
import glob

# Resolve the absolute path to the root directory's .env.local
current_dir = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(current_dir, '..', '.env.local')

# Manually parse the .env.local file if it exists
if os.path.exists(env_path):
    with open(env_path, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip() and not line.startswith('#'):
                try:
                    key, value = line.strip().split('=', 1)
                    os.environ[key.strip()] = value.strip()
                except ValueError:
                    continue

# Fetch the token after it has been loaded
GITHUB_TOKEN = os.getenv("GITHUB_ACCESS_KEY") 

if not GITHUB_TOKEN:
    raise ValueError("GitHub token not found! Please ensure it is set in the ../.env.local file.")

HEADERS = {"Authorization": f"Bearer {GITHUB_TOKEN}"}
BATCH_SIZE = 40 

print("Starting optimized parent commit fetch via GraphQL\n")

def get_latest_execution_folder(base_path="../executions"):
    if not os.path.exists(base_path):
        raise FileNotFoundError(f"Base directory not found: {base_path}")
        
    folders = [os.path.join(base_path, d) for d in os.listdir(base_path) if os.path.isdir(os.path.join(base_path, d))]
    if not folders:
        raise FileNotFoundError(f"Execution folder not found in {base_path}")
        
    return max(folders, key=os.path.getmtime)

EXECUTION_DIR = get_latest_execution_folder()
print(f"Using data from: {EXECUTION_DIR}")

BUILDS_FILE = os.path.join(EXECUTION_DIR, "raw_github_builds.csv")

if not os.path.exists(BUILDS_FILE):
    raise FileNotFoundError(f"File {BUILDS_FILE} not found.")

print("Reading builds file to extract tested merges...")
df_builds = pd.read_csv(BUILDS_FILE)

regex_merge = r"mining-framework-analysis_(?P<project>.+?)_(?P<commit>[a-f0-9]{40})_merge\."

unique_commits = set()

for _, row in df_builds.iterrows():
    branch = str(row.get('head_branch', ''))
    match = re.search(regex_merge, branch)
    if match:
        unique_commits.add((match.group('project'), match.group('commit')))

commits_list = list(unique_commits)
total_commits = len(commits_list)
total_batches = (total_commits // BATCH_SIZE) + (1 if total_commits % BATCH_SIZE != 0 else 0)

print(f"Extraction complete. Found {total_commits} unique merge commits.")
print(f"Processing in {total_batches} batches of up to {BATCH_SIZE} commits.\n")
print("-" * 60)

def build_graphql_query(batch):
    query_parts = []
    for i, (project, commit) in enumerate(batch):
        try:
            owner, name = project.split('/')
        except ValueError:
            continue
            
        part = f"""
        q{i}: repository(owner: "{owner}", name: "{name}") {{
            object(oid: "{commit}") {{
                ... on Commit {{
                    parents(first: 2) {{
                        nodes {{
                            oid
                        }}
                    }}
                }}
            }}
        }}
        """
        query_parts.append(part)
    return "query { " + "\n".join(query_parts) + " }"

results = []

for i in range(0, total_commits, BATCH_SIZE):
    current_batch = (i // BATCH_SIZE) + 1
    batch = commits_list[i:i + BATCH_SIZE]
    query = build_graphql_query(batch)
    
    print(f"[Batch {current_batch:02d}/{total_batches:02d}] Sending API request...", end="", flush=True)
    
    start_time = time.time()
    response = requests.post(
        "https://api.github.com/graphql", 
        json={'query': query}, 
        headers=HEADERS
    )
    elapsed_time = time.time() - start_time
    
    if response.status_code == 200:
        data = response.json().get('data', {})
        batch_successes = 0
        
        for index_str, repo_data in data.items():
            if not repo_data or not repo_data.get('object'):
                continue
                
            idx = int(index_str.replace('q', ''))
            project, commit = batch[idx]
            
            parents_nodes = repo_data['object']['parents']['nodes']
            parent_hashes = [p['oid'] for p in parents_nodes]
            
            p1 = parent_hashes[0] if len(parent_hashes) > 0 else None
            p2 = parent_hashes[1] if len(parent_hashes) > 1 else None
            
            results.append({
                'project': project,
                'commit': commit,
                'parent1': p1,
                'parent2': p2
            })
            batch_successes += 1
            
        print(f"\r[Batch {current_batch:02d}/{total_batches:02d}] Success ({elapsed_time:.1f}s) | Resolved: {batch_successes}/{len(batch)}")
    else:
        print(f"\r[Batch {current_batch:02d}/{total_batches:02d}] ERROR {response.status_code} ({elapsed_time:.1f}s) | Check Token or Rate Limit.")
        if response.status_code == 403 or response.status_code == 429:
            print("Rate limit reached. Pausing for 60 seconds...")
            time.sleep(60)

print("-" * 60)
print("Saving results to CSV...")

OUTPUT_FILE = os.path.join(EXECUTION_DIR, "commit_parents.csv")
df_parents = pd.DataFrame(results)
df_parents.to_csv(OUTPUT_FILE, index=False)

print(f"Process complete. Saved {len(results)} linked records to commit_parents.csv.")