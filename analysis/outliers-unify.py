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
    if pd.isna(val) or str(val).strip() == '': return 0.0
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
    except: return 0.0

print("MergirafSemi Unify Time Dissection by Termination Phase\n")
print(f"Using data from: {EXECUTION_DIR}")

for lang in languages:
    file_path = os.path.join(EXECUTION_DIR, "combined_csv", f"tools_{lang}.csv")
    if not os.path.exists(file_path): continue
    
    df = pd.read_csv(file_path)
    df.columns = df.columns.str.strip()
    
    tool = 'mergiraf_semi'
    df['p1_ms'] = df[f'phase1_time_{tool}'].apply(parse_time_to_ms)
    df['p2_ms'] = df[f'phase2_time_{tool}'].apply(parse_time_to_ms)
    df['p2_unify_ms'] = df[f'phase2_unify_time_{tool}'].apply(parse_time_to_ms)
    df['p3_ms'] = df[f'phase3_time_{tool}'].apply(parse_time_to_ms)
    df['p3_unify_ms'] = df[f'phase3_unify_time_{tool}'].apply(parse_time_to_ms)
    df['total_ms'] = df[f'total_merge_module_time_{tool}'].apply(parse_time_to_ms)

    df_p1 = df[df['p2_ms'] == 0]
    df_p2 = df[(df['p2_ms'] > 0) & (df['p3_ms'] == 0)]
    df_p3 = df[df['p3_ms'] > 0]
    
    df_p3_outliers = df_p3.nlargest(10, 'p3_ms')

    def get_stats(data):
        if data.empty: return "N/A", "N/A"
        total_avg = data['total_ms'].mean()
        unify_avg = (data['p2_unify_ms'] + data['p3_unify_ms']).mean()
        pct = (unify_avg / total_avg * 100) if total_avg > 0 else 0
        return f"{total_avg:>8.2f}ms", f"{unify_avg:>8.2f}ms ({pct:>5.1f}%)"

    print(f"\nLanguage: {lang.upper()}")
    print(f"{'Termination Scenario':<25} | {'Count':<6} | {'Avg Total':<12} | {'Avg Unify Time (% of total)'}")
    print("-" * 90)
    
    s1_t, s1_u = get_stats(df_p1)
    print(f"{'Finished in Phase 1':<25} | {len(df_p1):<6} | {s1_t} | {s1_u}")
    
    s2_t, s2_u = get_stats(df_p2)
    print(f"{'Finished in Phase 2':<25} | {len(df_p2):<6} | {s2_t} | {s2_u}")
    
    s3_t, s3_u = get_stats(df_p3)
    print(f"{'Finished in Phase 3':<25} | {len(df_p3):<6} | {s3_t} | {s3_u}")
    
    s3o_t, s3o_u = get_stats(df_p3_outliers)
    print(f"{'Top 10 Outliers (Phase 3)':<25} | {'10':<6} | {s3o_t} | {s3o_u}")
    print("-" * 90)