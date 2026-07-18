import pandas as pd
import numpy as np
import os
import re
import glob

print("Starting analysis for Research Questions (RQs)\n")

languages = ['java', 'py', 'js', 'rs', 'go']
lang_dir_map = {'java': 'java', 'py': 'python', 'js': 'js', 'rs': 'rust', 'go': 'go'}
base_tools = ['diff3', 's3m', 'mergiraf', 'mergiraf_semi']

def get_latest_execution_folder(base_path="../executions"):
    folders = [os.path.join(base_path, d) for d in os.listdir(base_path) if os.path.isdir(os.path.join(base_path, d))]
    if not folders:
        raise FileNotFoundError("Execution folder not found in ../executions")
    return max(folders, key=os.path.getmtime)

EXECUTION_DIR = get_latest_execution_folder()
print(f"Using data from: {EXECUTION_DIR}")

print("Loading raw_github_builds.csv...")
BUILDS_FILE = os.path.join(EXECUTION_DIR, "raw_github_builds.csv")

if os.path.exists(BUILDS_FILE):
    df_builds = pd.read_csv(BUILDS_FILE)
else:
    df_builds = pd.DataFrame(columns=['head_branch', 'conclusion'])
    print("Warning: raw_github_builds.csv not found.")

regex_tool = r"mining-framework-analysis_(?P<project>.+?)_(?P<commit>[a-f0-9]{40})_merge\.(?P<tool>.+?)\.(?P<lang>[a-zA-Z]+)"
regex_parent = r"mining-framework-analysis_(?P<project>.+?)_(?P<parent_hash>[a-f0-9]+)_parent_build"

build_tools_data = []
broken_parents = set()

for _, row in df_builds.iterrows():
    branch = str(row.get('head_branch', ''))
    conclusion = str(row.get('conclusion', '')).lower()
    
    match_tool = re.match(regex_tool, branch)
    if match_tool:
        d = match_tool.groupdict()
        build_tools_data.append({
            'project': d['project'],
            'commit': d['commit'],
            'tool': d['tool'],
            'build_conclusion': conclusion
        })
        continue
        
    match_parent = re.match(regex_parent, branch)
    if match_parent and conclusion == 'failure':
        d = match_parent.groupdict()
        broken_parents.add((d['project'], d['parent_hash']))

df_build_tools = pd.DataFrame(build_tools_data)

print("Loading why_build_failed.csv...")
REASONS_FILE = os.path.join(EXECUTION_DIR, "why_build_failed.csv")
forgiven_builds = set()

if os.path.exists(REASONS_FILE):
    df_reasons = pd.read_csv(REASONS_FILE)
    for _, row in df_reasons.iterrows():
        reason = str(row.get('fail_reason', ''))
        branch = str(row.get('branch', ''))
        
        if "Dependency/Environment" in reason or "Unavailable" in reason:
            match = re.match(regex_tool, branch)
            if match:
                d = match.groupdict()
                forgiven_builds.add((d['project'], d['commit'], d['tool']))
else:
    print("Warning: why_build_failed.csv not found.")

print("Loading commit_parents.csv...")
PARENTS_FILE = os.path.join(EXECUTION_DIR, "commit_parents.csv")
parents_map = {}
if os.path.exists(PARENTS_FILE):
    df_parents = pd.read_csv(PARENTS_FILE)
    for _, row in df_parents.iterrows():
        parents_map[(row['project'], row['commit'])] = [str(row['parent1']), str(row['parent2'])]

def verify_correctness(row, tool):
    status = str(row.get(f'status_{tool}')).strip()
    if status != 'SUCCESS_WITHOUT_CONFLICTS':
        return False
        
    if row.get(f'is_equal_{tool}', False):
        return True
        
    proj = row.get('project')
    commit = row.get('commit')
    
    if df_build_tools.empty:
        return False

    build_info = df_build_tools[(df_build_tools['project'] == proj) & 
                                (df_build_tools['commit'] == commit) & 
                                (df_build_tools['tool'] == tool)]
    
    if build_info.empty:
        return False
        
    if build_info.iloc[0]['build_conclusion'] == 'success':
        return True
    else:
        if (proj, commit, tool) in forgiven_builds:
            return True
            
        parents = parents_map.get((proj, commit), [])
        for parent_hash in parents:
            if parent_hash == 'nan' or parent_hash == 'None': continue
            if (proj, parent_hash) in broken_parents:
                return True
                
        return False

rq1_data, rq2_data, rq3_data = [], [], []

def calc_pairwise(df_lang, tool_a, tool_b, lang_name=""):
    if f'status_{tool_a}' not in df_lang.columns or f'status_{tool_b}' not in df_lang.columns:
        return 0, 0, 0, 0

    mask_a_conf_b_succ = (df_lang[f'status_{tool_a}'] == 'SUCCESS_WITH_CONFLICTS') & (df_lang[f'status_{tool_b}'] == 'SUCCESS_WITHOUT_CONFLICTS')
    df_c1 = df_lang[mask_a_conf_b_succ]
    
    df_afp_a = df_c1[df_c1[f'is_valid_{tool_b}'] == True]
    df_afn_b = df_c1[df_c1[f'is_valid_{tool_b}'] == False]
    
    afp_a = len(df_afp_a)
    afn_b = len(df_afn_b)

    mask_b_conf_a_succ = (df_lang[f'status_{tool_b}'] == 'SUCCESS_WITH_CONFLICTS') & (df_lang[f'status_{tool_a}'] == 'SUCCESS_WITHOUT_CONFLICTS')
    df_c2 = df_lang[mask_b_conf_a_succ]
    
    df_afp_b = df_c2[df_c2[f'is_valid_{tool_a}'] == True]
    df_afn_a = df_c2[df_c2[f'is_valid_{tool_a}'] == False]
    
    afp_b = len(df_afp_b)
    afn_a = len(df_afn_a)

    if lang_name:
        out_dir = os.path.join(EXECUTION_DIR, "detailed_fp_fn_reports")
        os.makedirs(out_dir, exist_ok=True)
        cols = ['project', 'commit', 'path']
        
        if not df_afp_a.empty: 
            df_afp_a[cols].to_csv(os.path.join(out_dir, f"{lang_name}_{tool_a}_aFP_vs_{tool_b}.csv"), index=False)
        if not df_afn_b.empty: 
            df_afn_b[cols].to_csv(os.path.join(out_dir, f"{lang_name}_{tool_b}_aFN_vs_{tool_a}.csv"), index=False)
        if not df_afp_b.empty: 
            df_afp_b[cols].to_csv(os.path.join(out_dir, f"{lang_name}_{tool_b}_aFP_vs_{tool_a}.csv"), index=False)
        if not df_afn_a.empty: 
            df_afn_a[cols].to_csv(os.path.join(out_dir, f"{lang_name}_{tool_a}_aFN_vs_{tool_b}.csv"), index=False)

    return afp_a, afn_a, afp_b, afn_b

for lang in languages:
    tools_file = os.path.join(EXECUTION_DIR, "combined_csv", f"tools_{lang}.csv")
        
    if not os.path.exists(tools_file):
        continue
        
    df = pd.read_csv(tools_file)
    df.columns = df.columns.str.strip()
    
    tools = base_tools.copy()
    if lang == 'java': tools.append('mergiraf_semi_plus')

    base_eq_dir = os.path.join(EXECUTION_DIR, "combined_csv", "output", "reports", "syntactic-comparison", lang_dir_map[lang])
    for tool in tools:
        eq_file = os.path.join(base_eq_dir, f"merge_{tool}_format_normalized_{lang}-merge_format_normalized_{lang}.csv")
        col_is_equal = f'is_equal_{tool}'
        
        if os.path.exists(eq_file):
            column_names = ['project', 'commit', 'path', 'path_tool', 'path_repo', 'is_equal']
            df_eq = pd.read_csv(eq_file, header=None, names=column_names)
            df_eq['is_equal_bool'] = df_eq['is_equal'].astype(str).str.strip().str.lower() == 'true'
            df = pd.merge(df, df_eq[['project', 'commit', 'path', 'is_equal_bool']], on=['project', 'commit', 'path'], how='left')
            df.rename(columns={'is_equal_bool': col_is_equal}, inplace=True)
            df[col_is_equal] = df[col_is_equal].fillna(False)
        else:
            df[col_is_equal] = False

    for tool in tools:
        if f'status_{tool}' in df.columns:
            df[f'is_valid_{tool}'] = df.apply(lambda r: verify_correctness(r, tool), axis=1)

    if lang == 'java':
        afp_semi, afn_semi, afp_plus, afn_plus = calc_pairwise(df, 'mergiraf_semi', 'mergiraf_semi_plus', lang_name=lang)
        rq1_data.append({
            'Lang': lang.upper(), 
            'aFP_MergirafSemi': afp_semi, 'aFN_MergirafSemi': afn_semi, 
            'aFP_MergirafSemi+': afp_plus, 'aFN_MergirafSemi+': afn_plus
        })

    afp_semi_rq2, afn_semi_rq2, afp_estruturado, afn_estruturado = calc_pairwise(df, 'mergiraf_semi', 'mergiraf', lang_name=lang)
    rq2_data.append({
        'Lang': lang.upper(), 
        'aFP_MergirafSemi': afp_semi_rq2, 'aFN_MergirafSemi': afn_semi_rq2, 
        'aFP_Structured': afp_estruturado, 'aFN_Structured': afn_estruturado
    })

    afp_s3m, afn_s3m, afp_semi_rq3a, afn_semi_rq3a = calc_pairwise(df, 's3m', 'mergiraf_semi', lang_name=lang)
    afp_semi_rq3b, afn_semi_rq3b, afp_diff3, afn_diff3 = calc_pairwise(df, 'mergiraf_semi', 'diff3', lang_name=lang)

    rq3_data.append({
        'Lang': lang.upper(), 
        'aFP_S3M(vs_Semi)': afp_s3m, 'aFN_S3M(vs_Semi)': afn_s3m,
        'aFP_Semi(vs_S3M)': afp_semi_rq3a, 'aFN_Semi(vs_S3M)': afn_semi_rq3a,
        'aFP_Semi(vs_Diff3)': afp_semi_rq3b, 'aFN_Semi(vs_Diff3)': afn_semi_rq3b,
        'aFP_Diff3(vs_Semi)': afp_diff3, 'aFN_Diff3(vs_Semi)': afn_diff3
    })

print("="*90)
print("RQ1: What is the impact of node ordering configuration on the accuracy of MergirafSemi?")
print("     Direct Comparison: MergirafSemi vs MergirafSemi+")
print("="*90)
df_rq1 = pd.DataFrame(rq1_data).set_index('Lang') if rq1_data else pd.DataFrame()
print(df_rq1.to_string())

print("\n" + "="*90)
print("RQ2: What is the impact of structural granularity on merge accuracy and runtime?")
print("     Direct Comparison: MergirafSemi (Semistructured) vs Mergiraf (Structured)")
print("="*90)
df_rq2 = pd.DataFrame(rq2_data).set_index('Lang') if rq2_data else pd.DataFrame()
print(df_rq2.to_string())

print("\n" + "="*90)
print("RQ3: How does a language-agnostic semistructured tool compare to specific and unstructured?")
print("     Direct Comparison: S3M vs MergirafSemi  |  MergirafSemi vs Diff3")
print("="*90)
df_rq3 = pd.DataFrame(rq3_data).set_index('Lang') if rq3_data else pd.DataFrame()
print(df_rq3.to_string())
print("="*90)