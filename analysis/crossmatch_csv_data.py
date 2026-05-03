import pandas as pd
import os
import glob

print("Starting pairwise scenario combination (Strict Inner Join)\n")
print("=" * 80)

languages = ['java', 'py', 'go', 'js', 'rs']
base_tools = ['diff3', 'mergiraf', 'mergiraf_semi', 'mergiraf_semi_plus']

def get_latest_execution_folder(base_path="../executions"):
    if not os.path.exists(base_path):
        raise FileNotFoundError(f"Base directory not found: {base_path}")
        
    folders = [os.path.join(base_path, d) for d in os.listdir(base_path) if os.path.isdir(os.path.join(base_path, d))]
    if not folders:
        raise FileNotFoundError(f"Execution folder not found in {base_path}")
        
    return max(folders, key=os.path.getmtime)

EXECUTION_DIR = get_latest_execution_folder()
print(f"Using data from: {EXECUTION_DIR}")

csv_columns = [
    'project', 'commit', 'path', 'tool_file', 'status', 'time',
    'phase1_time', 'phase2_time', 'phase2_unify_time', 'phase2_diffy_calls', 
    'phase2_diffy_time', 'phase3_time', 'phase3_unify_time', 
    'phase3_diffy_calls', 'phase3_diffy_time', 'total_merge_module_time'
]
join_keys = ['project', 'commit', 'path']

combined_out_dir = os.path.join(EXECUTION_DIR, "combined_csv")
os.makedirs(combined_out_dir, exist_ok=True)

for lang in languages:
    tools = base_tools.copy()
    if lang == 'java':
        tools.append('s3m')
        
    df_master = None
    
    print(f"\nProcessing ecosystem: {lang.upper()}")
    
    for tool in tools:
        csv_file = os.path.join(EXECUTION_DIR, "reports", lang, f"{tool}.csv")
        
        if not os.path.exists(csv_file):
            print(f"    Warning: File {csv_file} not found. Skipping tool.")
            continue
            
        df_temp = pd.read_csv(csv_file, header=None, names=csv_columns)
        df_temp = df_temp.drop(columns=['tool_file'])
        
        columns_to_rename = [col for col in df_temp.columns if col not in join_keys]
        df_temp = df_temp.rename(columns={col: f'{col}_{tool}' for col in columns_to_rename})
        
        print(f"  - {tool} loaded: {len(df_temp)} files analyzed.")
        
        if df_master is None:
            df_master = df_temp
        else:
            df_master = pd.merge(df_master, df_temp, on=join_keys, how='inner')

    if df_master is not None:
        status_columns = [col for col in df_master.columns if col.startswith('status_')]
        df_master[status_columns] = df_master[status_columns].fillna('CRASH_OR_TIMEOUT')
        
        output_file = os.path.join(combined_out_dir, f"tools_{lang}.csv")
        df_master.to_csv(output_file, index=False)
        print(f"  Master table generated: {output_file}")
        print(f"  Scenarios kept after inner join: {len(df_master)}")
        
print("\n" + "=" * 80)
print("Combination finished. Dataset is paired and ready for statistical analysis.")