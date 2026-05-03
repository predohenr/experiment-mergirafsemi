import pandas as pd
import numpy as np
import os
import re
import glob

def get_latest_execution_folder(base_path="../executions"):
    if not os.path.exists(base_path):
        raise FileNotFoundError(f"Base directory not found: {base_path}")
    folders = [os.path.join(base_path, d) for d in os.listdir(base_path) if os.path.isdir(os.path.join(base_path, d))]
    if not folders:
        raise FileNotFoundError(f"Execution folder not found in {base_path}")
    return max(folders, key=os.path.getmtime)

EXECUTION_DIR = get_latest_execution_folder()
languages = ['java', 'py', 'go', 'js', 'rs']

def parse_time_to_ms(val):
    if pd.isna(val) or str(val).strip() == '': return np.nan
    val_str = str(val).strip()
    match = re.match(r"([\d\.]+)([a-zA-Zµ]+)", val_str)
    if match:
        num, unit = float(match.group(1)), match.group(2)
        if unit == 'ms': return num
        elif unit in ['µs', 'us']: return num / 1000.0
        elif unit == 'ns': return num / 1000000.0
        elif unit == 's': return num * 1000.0
        else: return num
    try: return float(val_str) / 1000000.0
    except: return np.nan

print("Deep Dive: Analyzing Phase 3 Extreme Outliers\n")
print(f"Using data from: {EXECUTION_DIR}")

for lang in languages:
    file_path = os.path.join(EXECUTION_DIR, "combined_csv", f"tools_{lang}.csv")
    if not os.path.exists(file_path): 
        continue
    
    df = pd.read_csv(file_path)
    df.columns = df.columns.str.strip()
    
    for tool in ['mergiraf', 'mergiraf_semi']:
        for phase in ['1', '2', '3']:
            df[f'p{phase}_{tool}_ms'] = df[f'phase{phase}_time_{tool}'].apply(parse_time_to_ms).fillna(0)
        df[f'total_{tool}_ms'] = df[f'total_merge_module_time_{tool}'].apply(parse_time_to_ms).fillna(0)

    worst_p3_semi = df.nlargest(50, 'p3_mergiraf_semi_ms')

    print(f"\nLanguage: {lang.upper()} - Top 50 Phase 3 Outliers (MergirafSemi)")
    print(f"{'Short Path':<30} | {'Semi P3 (ms)':<15} | {'Mergiraf P3 (ms)':<15} | {'Resolved in P2?'}")
    print("-" * 90)

    count_resolved_p2 = 0
    for _, row in worst_p3_semi.iterrows():
        short_path = row['path'].split('/')[-1][:30]
        p3_semi = row['p3_mergiraf_semi_ms']
        p3_merg = row['p3_mergiraf_ms']
        
        resolved_p2 = "YES" if p3_merg == 0 else "NO"
        if p3_merg == 0: count_resolved_p2 += 1
        
        print(f"{short_path:<30} | {p3_semi:>12.2f} ms | {p3_merg:>12.2f} ms | {resolved_p2}")

    print(f"\nResult: In {count_resolved_p2} out of the 50 worst cases, Mergiraf resolved before Phase 3.")
    print("-" * 90 + "\n")