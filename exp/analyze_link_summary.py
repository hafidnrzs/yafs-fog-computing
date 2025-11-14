
"""
Summarize YAFS link-level results (results_*_link.csv) per your spec.
Outputs:
- hotspots_links.csv (src, dst, count, latency, throughput)
- adra_adsa_avg.csv
- node_load_balance.csv
- summary_global.csv
- plots: plot_hotspots_by_count.png, plot_hotspots_by_latency.png, plot_hotspots_by_throughput.png

python analisis/analyze_link_summary.py --csv /Users/adhitya/Project/exp/results/results_CN_1000000_link.csv --algo CN --outdir /Users/adhitya/Project/exp/analisis/5_evaluasi/CN/CN_link
"""

import argparse
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path

def ensure_numeric(df, cols):
    for c in cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors='coerce')
    return df

def main(csv_path: str, algo: str, outdir: str, topk: int = 25):
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(csv_path)
    expected = ['id','type','src','dst','app','latency','message','ctime','size','buffer']
    missing = [c for c in expected if c not in df.columns]
    if missing:
        raise ValueError(f'Missing expected columns in {csv_path}: {missing}')

    df = ensure_numeric(df, ['id','src','dst','app','latency','ctime','size','buffer'])

    # Hotspot links
    per_link = df.groupby(['src','dst']).agg(
        count=('id','count'),
        latency=('latency','mean'),
        bytes=('size','sum'),
        tmin=('ctime','min'),
        tmax=('ctime','max')
    ).reset_index()
    per_link['window'] = (per_link['tmax'] - per_link['tmin']).replace(0, np.nan)
    per_link['throughput'] = per_link['bytes'] / per_link['window']
    per_link['throughput'] = per_link['throughput'].fillna(0.0)
    hotspots = per_link[['src','dst','count','latency','throughput']]
    hotspots.to_csv(outdir / 'hotspots_links.csv', index=False)

    # ADRA/ADSA avg
    is_user = df['message'].astype(str).str.startswith('M.USER')
    avg_adra = float(df.loc[is_user, 'latency'].mean()) if is_user.any() else np.nan
    avg_adsa = float(df.loc[~is_user, 'latency'].mean()) if (~is_user).any() else np.nan
    pd.DataFrame({'algorithm':[algo], 'avg_ADRA_latency':[avg_adra], 'avg_ADSA_latency':[avg_adsa]}).to_csv(outdir / 'adra_adsa_avg.csv', index=False)

    # Node load balance
    tx = df['src'].value_counts().rename('tx_count')
    rx = df['dst'].value_counts().rename('rx_count')
    load = pd.concat([tx, rx], axis=1).fillna(0)
    load['total'] = load['tx_count'] + load['rx_count']
    load.reset_index().rename(columns={'index':'node_id'}).to_csv(outdir / 'node_load_balance.csv', index=False)

    # Summary
    avg_latency_global = float(df['latency'].mean())
    total_messages = int(len(df))
    min_size = float(df['size'].min()) if total_messages else np.nan
    max_size = float(df['size'].max()) if total_messages else np.nan
    avg_size = float(df['size'].mean()) if total_messages else np.nan
    tmin, tmax = df['ctime'].min(), df['ctime'].max()
    window = (tmax - tmin) if pd.notnull(tmax) and pd.notnull(tmin) else np.nan
    avg_throughput = (total_messages / window) if (window and window > 0) else np.nan
    pd.DataFrame({
        'algorithm':[algo],
        'avg_latency_global':[avg_latency_global],
        'avg_ADRA':[avg_adra],
        'avg_ADSA':[avg_adsa],
        'avg_throughput':[avg_throughput],
        'total_messages':[total_messages],
        'min_size':[min_size],
        'max_size':[max_size],
        'avg_size':[avg_size]
    }).to_csv(outdir / 'summary_global.csv', index=False)

    # Plots
    import matplotlib
    plt.figure()
    top_by_count = hotspots.sort_values('count', ascending=False).head(topk)
    if not top_by_count.empty:
        labels = [f"{int(r.src)}→{int(r.dst)}" for _, r in top_by_count.iterrows()]
        plt.bar(labels, top_by_count['count'].values)
        plt.xticks(rotation=75)
        plt.ylabel('Count')
        plt.title(f'Top {topk} Links by Count - {algo}')
        plt.tight_layout()
        plt.savefig(outdir / 'plot_hotspots_by_count.png', dpi=160)
        plt.close()

    top_by_latency = hotspots.sort_values('latency', ascending=False).head(topk)
    if not top_by_latency.empty:
        plt.figure()
        labels = [f"{int(r.src)}→{int(r.dst)}" for _, r in top_by_latency.iterrows()]
        plt.bar(labels, top_by_latency['latency'].values)
        plt.xticks(rotation=75)
        plt.ylabel('Average Latency (per-hop)')
        plt.title(f'Top {topk} Links by Avg Latency - {algo}')
        plt.tight_layout()
        plt.savefig(outdir / 'plot_hotspots_by_latency.png', dpi=160)
        plt.close()

    top_by_tp = hotspots.sort_values('throughput', ascending=False).head(topk)
    if not top_by_tp.empty:
        plt.figure()
        labels = [f"{int(r.src)}→{int(r.dst)}" for _, r in top_by_tp.iterrows()]
        plt.bar(labels, top_by_tp['throughput'].values)
        plt.xticks(rotation=75)
        plt.ylabel('Throughput (bytes / time)')
        plt.title(f'Top {topk} Links by Throughput - {algo}')
        plt.tight_layout()
        plt.savefig(outdir / 'plot_hotspots_by_throughput.png', dpi=160)
        plt.close()

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--csv', required=True, help='Path to results_*_link.csv')
    parser.add_argument('--algo', required=True, help='Algorithm label, e.g., ILP or WCN')
    parser.add_argument('--outdir', required=True, help='Directory to write outputs')
    parser.add_argument('--topk', type=int, default=25, help='Top-K for hotspot plots')
    args = parser.parse_args()
    main(args.csv, args.algo, args.outdir, args.topk)
