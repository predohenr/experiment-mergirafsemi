import csv
import os
import glob

def get_latest_execution_folder(base_path="../executions"):
    if not os.path.exists(base_path):
        raise FileNotFoundError(f"Base directory not found: {base_path}")
        
    folders = [os.path.join(base_path, d) for d in os.listdir(base_path) if os.path.isdir(os.path.join(base_path, d))]
    if not folders:
        raise FileNotFoundError(f"Execution folder not found in {base_path}")
        
    return max(folders, key=os.path.getmtime)

EXECUTION_DIR = get_latest_execution_folder()

# Configuration
LANGUAGE = 'java'
BASE_TOOL = 'mergiraf'
COMPARISON_TOOL = 's3m'

BASE_FILE = os.path.join(EXECUTION_DIR, 'reports', LANGUAGE, f'{BASE_TOOL}.csv')
COMPARISON_FILE = os.path.join(EXECUTION_DIR, 'reports', LANGUAGE, f'{COMPARISON_TOOL}.csv')
OUTPUT_FILE = os.path.join(EXECUTION_DIR, f'missing_scenarios_{COMPARISON_TOOL}.txt')

def extract_scenarios(csv_path):
    scenarios = set()
    try:
        with open(csv_path, mode='r', encoding='utf-8') as f:
            reader = csv.reader(f)
            for row in reader:
                if len(row) > 2: 
                    scenario_id = row[2].strip()
                    scenarios.add(scenario_id)
    except FileNotFoundError:
        print(f"Error: File {csv_path} not found.")
    return scenarios

def main():
    print(f"Using data from: {EXECUTION_DIR}")
    print("Analyzing CSV files...\n")
    
    base_scenarios = extract_scenarios(BASE_FILE)
    comparison_scenarios = extract_scenarios(COMPARISON_FILE)
    
    print(f"Total in {BASE_TOOL}: {len(base_scenarios)}")
    print(f"Total in {COMPARISON_TOOL}: {len(comparison_scenarios)}")
    
    missing = base_scenarios - comparison_scenarios
    
    print(f"\nFound {len(missing)} missing scenarios.")
    
    if missing:
        with open(OUTPUT_FILE, mode='w', encoding='utf-8') as f:
            for scenario in sorted(missing):
                f.write(f"{scenario}\n")
        print(f"List saved to: {OUTPUT_FILE}")

if __name__ == '__main__':
    main()