import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import os

# Standardizing plot settings for the paper
sns.set_theme(style="whitegrid")
plt.rcParams.update({'font.size': 16, 'axes.labelsize': 16, 'xtick.labelsize': 16, 'ytick.labelsize': 16})

def get_latest_execution_folder(base_path="../executions"):
    if not os.path.exists(base_path):
        raise FileNotFoundError(f"Base directory not found: {base_path}")
    folders = [os.path.join(base_path, d) for d in os.listdir(base_path) if os.path.isdir(os.path.join(base_path, d))]
    if not folders:
        raise FileNotFoundError(f"Execution folder not found in {base_path}")
    return max(folders, key=os.path.getmtime)

EXECUTION_DIR = get_latest_execution_folder()
languages = ['java', 'rs', 'go', 'js', 'py']

# Configuration for tools and naming
formatted_names = {
    'mergiraf_semi': 'MergirafSemi',
    'mergiraf_semi_plus': 'MergirafSemi+',
    'mergiraf': 'Mergiraf',
    'diff3': 'diff3',
    's3m': 'S3M'
}

print(f"Using data from: {EXECUTION_DIR}")
os.makedirs('images', exist_ok=True)

global_scenario_count = 0
global_successes = {t: 0 for t in formatted_names.keys()}

for lang in languages:
    file_path = os.path.join(EXECUTION_DIR, "combined_csv", f"tools_{lang}.csv")
    if not os.path.exists(file_path):
        continue
        
    df = pd.read_csv(file_path)
    total_scenarios = len(df)
    global_scenario_count += total_scenarios
    
    available_tools = [t for t in formatted_names.keys() if f'status_{t}' in df.columns]
    
    accuracy_data = {}
    
    print("-" * 80)
    print(f"LANGUAGE: {lang.upper()} (Total Scenarios: {total_scenarios})")
    
    for tool in available_tools:
        successes = len(df[df[f'status_{tool}'] == 'SUCCESS_WITHOUT_CONFLICTS'])
        rate = (successes / total_scenarios) * 100
        accuracy_data[tool] = rate
        global_successes[tool] += successes

    # Local Graph Generation
    labels = [formatted_names[t] for t in available_tools]
    accuracy_values = [accuracy_data[t] for t in available_tools]

    plt.figure(figsize=(10, 6))
    ax = sns.barplot(x=labels, y=accuracy_values, palette="Blues_d")
    
    # Title removed per instructions. Font size 16 for labels.
    plt.ylim(0, 100)
    plt.ylabel("Resolution Rate (%)")
    
    for i, v in enumerate(accuracy_values):
        ax.text(i, v + 1, f"{v:.2f}%", ha='center', va='bottom', fontweight='bold', fontsize=14)

    plt.tight_layout()
    local_output = f'images/graph_resolution_rate_{lang}.pdf'
    plt.savefig(local_output)
    plt.close()

# Global Aggregated Graph
if global_scenario_count > 0:
    print("\n" + "=" * 80)
    print(f"Generating global aggregated results (Total files: {global_scenario_count})")
    
    # The user must edit this chart by choosing the tools and the order in which they should appear.
    # The order must be: diff3, S3M (s3m), Mergiraf, MergirafSemi (mergiraf_semi) and MergirafSemi+ (mergiraf_semi_plus)
    chart_tools = ['diff3', 's3m', 'mergiraf', 'mergiraf_semi', 'mergiraf_semi_plus']
    
    global_labels = [formatted_names[t] for t in chart_tools]
    global_accuracy = [(global_successes[t] / global_scenario_count) * 100 for t in chart_tools]

    plt.figure(figsize=(12, 7))
    ax_global = sns.barplot(x=global_labels, y=global_accuracy, palette="Blues_d")
    
    plt.ylim(0, 100)
    plt.ylabel("Resolution Rate (%)")
    
    for i, v in enumerate(global_accuracy):
        ax_global.text(i, v + 1, f"{v:.2f}%", ha='center', va='bottom', fontweight='bold', fontsize=14)

    plt.tight_layout()
    global_output = 'images/graph_resolution_rate_ALL_LANGUAGES.pdf'
    plt.savefig(global_output)
    plt.close()
    
    print(f"Global graph saved: {global_output}")

print("\nProcess finished.")