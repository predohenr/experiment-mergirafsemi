import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import ptitprince as pt
import os
import glob

# Standardizing style for academic publication
sns.set_theme(style="whitegrid")
plt.rcParams.update({
    'font.size': 18, 
    'axes.labelsize': 16, 
    'xtick.labelsize': 16, 
    'ytick.labelsize': 16
})

def get_latest_execution_folder(base_path="../executions"):
    if not os.path.exists(base_path):
        raise FileNotFoundError(f"Base directory not found: {base_path}")
    folders = [os.path.join(base_path, d) for d in os.listdir(base_path) if os.path.isdir(os.path.join(base_path, d))]
    if not folders:
        raise FileNotFoundError(f"Execution folder not found in {base_path}")
    return max(folders, key=os.path.getmtime)

EXECUTION_DIR = get_latest_execution_folder()
languages = ['java', 'py', 'go', 'js', 'rs']

# Configuration for naming
formatted_names = {
    'mergiraf_semi': 'MergirafSemi',
    'mergiraf_semi_plus': 'MergirafSemi+',
    'mergiraf': 'Mergiraf',
    'diff3': 'diff3',
    's3m': 'S3M'
}

print(f"Using data from: {EXECUTION_DIR}")
os.makedirs('images', exist_ok=True)

global_time_data = []

for lang in languages:
    file_path = os.path.join(EXECUTION_DIR, "combined_csv", f"tools_{lang}.csv")
    if not os.path.exists(file_path):
        continue
        
    df = pd.read_csv(file_path)
    available_tools = [col.replace('status_', '') for col in df.columns if col.startswith('status_')]
    
    # Tool selection for local plots
    plot_tools = [t for t in formatted_names.keys() if t in available_tools]
    
    lang_time_data = [] 
    
    for tool in plot_tools:
        # Measuring performance only for successful scenarios
        success_mask = df[f'status_{tool}'] == 'SUCCESS_WITHOUT_CONFLICTS'
        if f'time_{tool}' in df.columns:
            times = pd.to_numeric(df[success_mask][f'time_{tool}'], errors='coerce').dropna() / 1e6
            
            for t in times:
                entry = {'Tool': formatted_names[tool], 'Time (ms)': t}
                lang_time_data.append(entry)
                global_time_data.append(entry)

    # Local RainCloud Plots Generation
    if lang_time_data:
        plt.figure(figsize=(10, 6))
        local_order = [formatted_names[t] for t in plot_tools]
        
        ax = pt.RainCloud(
            x='Tool', y='Time (ms)', 
            data=pd.DataFrame(lang_time_data), 
            palette="Set2", 
            order=local_order,
            bw=0.2, width_viol=0.6, orient='h', alpha=0.6, 
            dodge=False, pointplot=False, move=0.2
        )
        
        # Displaying median values on the plot
        for i, tool_name in enumerate(local_order):
            df_temp = pd.DataFrame(lang_time_data)
            med_local = df_temp[df_temp['Tool'] == tool_name]['Time (ms)'].median()
            if pd.notna(med_local) and med_local > 0:
                ax.text(
                    med_local, i + 0.15, f" {med_local:.1f} ms ", 
                    va='top', ha='center', fontsize=12, fontweight='bold', color='black',
                    bbox=dict(facecolor='white', alpha=0.7, edgecolor='none', pad=1)
                )

        plt.xlabel('Time (ms)')
        plt.ylabel('')
        plt.xscale('log')
        plt.grid(True, which="both", ls="--", alpha=0.3)
        plt.tight_layout()
        
        output_local = f'images/graph_time_{lang}.pdf'
        plt.savefig(output_local, bbox_inches='tight')
        plt.close()

# Global Aggregated Boxplot
df_global = pd.DataFrame(global_time_data)

if not df_global.empty:
    print("Generating global aggregated boxplot...")
    plt.figure(figsize=(12, 7))
    
    # The user must edit this chart by choosing the tools and the order in which they should appear.
    # Suggested order: diff3, S3M (s3m), Mergiraf, MergirafSemi (mergiraf_semi) and MergirafSemi+ (mergiraf_semi_plus)
    chart_tools = ['mergiraf_semi', 'mergiraf']
    
    global_order = [formatted_names[t] for t in chart_tools if formatted_names[t] in df_global['Tool'].unique()]
    
    ax_box = sns.boxplot(
        x='Time (ms)', 
        y='Tool', 
        data=df_global, 
        palette="Set2",
        order=global_order,
        linewidth=1.5,
        fliersize=3
    )
    
    # Displaying global median values
    for i, tool_name in enumerate(global_order):
        med_global = df_global[df_global['Tool'] == tool_name]['Time (ms)'].median()
        if pd.notna(med_global) and med_global > 0:
            ax_box.text(
                med_global, i - 0.25, f" {med_global:.1f} ms ", 
                va='center', ha='center', fontsize=12, fontweight='bold', color='black',
                bbox=dict(facecolor='white', alpha=0.9, edgecolor='black', boxstyle='round,pad=0.2')
            )

    plt.xlabel('Time (ms)')
    plt.ylabel('')
    plt.xscale('log')
    plt.grid(True, which="both", ls="--", alpha=0.3)
    plt.tight_layout()
    
    output_global = 'images/graph_time_ALL_LANGUAGES_BOXPLOT.pdf'
    plt.savefig(output_global, bbox_inches='tight')
    plt.close()

print("\nProcess finished.")