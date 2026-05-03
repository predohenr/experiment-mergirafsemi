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
analysis_tools = ['mergiraf', 'mergiraf_semi']

print("Starting execution pipeline profiling with quartiles\n")
print(f"Using data from: {EXECUTION_DIR}")

def parse_time_to_ms(val):
    if pd.isna(val) or str(val).strip() == '':
        return np.nan
    val_str = str(val).strip()
    match = re.match(r"([\d\.]+)([a-zA-Zµ]+)", val_str)
    
    if match:
        num = float(match.group(1))
        unit = match.group(2)
        if unit == 'ms': return num
        elif unit in ['µs', 'us']: return num / 1000.0
        elif unit == 'ns': return num / 1000000.0
        elif unit == 's': return num * 1000.0
        elif unit == 'm': return num * 60000.0
        else: return num
    else:
        try: return float(val_str) / 1000000.0
        except: return np.nan

csv_data = []

for lang in languages:
    file_path = os.path.join(EXECUTION_DIR, "combined_csv", f"tools_{lang}.csv")
    if not os.path.exists(file_path):
        continue
        
    df = pd.read_csv(file_path)
    df.columns = df.columns.str.strip()
    
    print("\n" + "=" * 90)
    print(f"LANGUAGE: {lang.upper()}")
    print("=" * 90)
    
    for tool in analysis_tools:
        if f'status_{tool}' not in df.columns:
            continue
            
        valid_status = ['SUCCESS_WITHOUT_CONFLICTS', 'SUCCESS_WITH_CONFLICTS']
        df_valid = df[df[f'status_{tool}'].isin(valid_status)].copy()
        
        if df_valid.empty: 
            continue
            
        print(f"\nTOOL: {tool.upper()} ({len(df_valid)} processed scenarios)")
        
        # Performance metrics calculation
        total_time = df_valid[f'total_merge_module_time_{tool}'].apply(parse_time_to_ms).dropna()
        p1_time = df_valid[f'phase1_time_{tool}'].apply(parse_time_to_ms).dropna() if f'phase1_time_{tool}' in df_valid.columns else pd.Series(dtype=float)
        p2_time = df_valid[f'phase2_time_{tool}'].apply(parse_time_to_ms).dropna() if f'phase2_time_{tool}' in df_valid.columns else pd.Series(dtype=float)
        p3_time = df_valid[f'phase3_time_{tool}'].apply(parse_time_to_ms).dropna() if f'phase3_time_{tool}' in df_valid.columns else pd.Series(dtype=float)
        
        csv_data.append({
            'Language': lang.upper(),
            'Tool': tool,
            'Total_Mean': total_time.mean() if not total_time.empty else np.nan,
            'Total_Median': total_time.median() if not total_time.empty else np.nan,
            'Total_StdDev': total_time.std() if not total_time.empty else np.nan,
            'Phase1_Mean': p1_time.mean() if not p1_time.empty else np.nan,
            'Phase1_Median': p1_time.median() if not p1_time.empty else np.nan,
            'Phase1_StdDev': p1_time.std() if not p1_time.empty else np.nan,
            'Phase2_Mean': p2_time.mean() if not p2_time.empty else np.nan,
            'Phase2_Median': p2_time.median() if not p2_time.empty else np.nan,
            'Phase2_StdDev': p2_time.std() if not p2_time.empty else np.nan,
            'Phase3_Mean': p3_time.mean() if not p3_time.empty else np.nan,
            'Phase3_Median': p3_time.median() if not p3_time.empty else np.nan,
            'Phase3_StdDev': p3_time.std() if not p3_time.empty else np.nan
        })

        # Console reporting logic
        time_cols = ['phase1_time', 'phase2_time', 'phase2_unify_time', 'phase2_diffy_time',
                     'phase3_time', 'phase3_unify_time', 'phase3_diffy_time', 'total_merge_module_time']
        call_cols = ['phase2_diffy_calls', 'phase3_diffy_calls']
        
        median_results = {}
        q1_results = {}
        q3_results = {}
        call_results = {}
        
        for col in time_cols:
            col_name = f"{col}_{tool}"
            if col_name in df_valid.columns:
                values_ms = df_valid[col_name].apply(parse_time_to_ms).dropna()
                values_ms = values_ms[values_ms > 0]
                
                if not values_ms.empty:
                    median_results[col] = values_ms.median()
                    q1_results[col] = values_ms.quantile(0.25)
                    q3_results[col] = values_ms.quantile(0.75)
                else:
                    median_results[col] = 0.0
                    q1_results[col] = 0.0
                    q3_results[col] = 0.0
            
        for col in call_cols:
            col_name = f"{col}_{tool}"
            if col_name in df_valid.columns:
                call_values = pd.to_numeric(df_valid[col_name], errors='coerce').fillna(0)
                call_results[col] = call_values.mean() if not call_values.empty else 0.0

        def fmt_time(col_name):
            med = median_results.get(col_name, 0)
            if med == 0.0:
                return "0.00 ms"
            q1 = q1_results.get(col_name, 0)
            q3 = q3_results.get(col_name, 0)
            return f"{med:.2f} ms [Q1: {q1:.2f} | Q3: {q3:.2f}]"

        print(f"   Total Module Time: {fmt_time('total_merge_module_time')}")
        print(f"      Phase 1 (Line-based / diff3):       {fmt_time('phase1_time')}")
        print(f"      Phase 2 (Structured on Conflicts):  {fmt_time('phase2_time')}")
        print(f"         Unify:                           {fmt_time('phase2_unify_time')}")
        print(f"         Diffy (Text Fallback):           {fmt_time('phase2_diffy_time')} (Mean: {call_results.get('phase2_diffy_calls', 0):.1f} calls)")
        print(f"      Phase 3 (Structured Whole File):    {fmt_time('phase3_time')}")
        print(f"         Unify:                           {fmt_time('phase3_unify_time')}")
        print(f"         Diffy (Text Fallback):           {fmt_time('phase3_diffy_time')} (Mean: {call_results.get('phase3_diffy_calls', 0):.1f} calls)")

# Save tabular data
output_metrics_file = os.path.join(EXECUTION_DIR, "time_metrics_by_phase.csv")
df_output = pd.DataFrame(csv_data)
df_output.to_csv(output_metrics_file, index=False)

print("\n" + "=" * 90)
print("Time profiling and quartile analysis finished.")
print(f"Tabular data saved to: {output_metrics_file}")