
"""
Analyze YAFS end-to-end results (results_*.csv).

Now with robust --entities support to compute layer-based summaries.

Inputs:
- --csv: path to results_*.csv (end-to-end events)
- --algo: label for the algorithm (e.g., ILP, WCN)
- --outdir: output folder
- --bin_width: throughput time bin size (default 100)
- --entities: optional CSV mapping nodes to layers; accepted columns (any one for id): id_resource | node_id | id
             required column: node_type (e.g., FG, FOG, CFG, CLOUD)

Outputs (CSVs in --outdir):
- summary_global.csv
- e2e_latency_per_app.csv
- response_time_per_app.csv
- processing_time_per_module.csv                (if 'module' exists)
- network_delay_per_link.csv                    (if TOPO.src/dst exist)
- throughput_overall.csv
- throughput_timebins_w<bin>.csv
- layer_performance.csv                         (requires --entities; avg E2E per node_type of TOPO.dst)
- layer_link_summary.csv                        (requires --entities; avg network_delay by src_type→dst_type)
- entities_coverage_report.csv                  (requires --entities; shows join coverage stats)

"""

import argparse
from pathlib import Path
import pandas as pd
import numpy as np

def ensure_numeric(df, cols):
    for c in cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors='coerce')
    return df

def load_entities(entities_path: str):
    ent = pd.read_csv(entities_path)
    # Accept flexible id column names
    id_cols = [c for c in ['id_resource','node_id','id'] if c in ent.columns]
    if not id_cols:
        raise ValueError("Entities CSV must include one of: id_resource, node_id, id")
    id_col = id_cols[0]
    if 'node_type' not in ent.columns:
        if 'type' in ent.columns:
            ent = ent.rename(columns={'type':'node_type'})
        else:
            raise ValueError("Entities CSV must include 'node_type' (or alias 'type') column")
    out = ent[[id_col, 'node_type']].copy()
    out = out.dropna().copy()
    out[id_col] = pd.to_numeric(out[id_col], errors='coerce')
    out = out.dropna(subset=[id_col])
    out[id_col] = out[id_col].astype(int)
    # Normalize node_type to uppercase trimmed
    out['node_type'] = out['node_type'].astype(str).str.strip().str.upper()
    out = out.rename(columns={id_col: 'id_resource'})
    return out

def main(csv_path: str, algo: str, outdir: str, bin_width: float = 100.0, entities_path: str = None):
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(csv_path)

    # Required columns
    required = ['app','time_emit','time_reception','time_in','time_out']
    miss = [c for c in required if c not in df.columns]
    if miss:
        raise ValueError(f"Missing required columns in {csv_path}: {miss}")

    time_cols = ['time_emit','time_reception','time_in','time_out']
    topo_cols = [c for c in ['TOPO.src','TOPO.dst'] if c in df.columns]
    num_cols = time_cols + topo_cols + ['app'] + (['module'] if 'module' in df.columns else [])
    df = ensure_numeric(df, num_cols)

    # Derived
    df['E2E_latency']     = df['time_reception'] - df['time_emit']
    df['processing_time'] = df['time_out'] - df['time_in']
    df['network_delay']   = (df['time_in'] - df['time_emit']).abs()

    # Global
    total_msgs = int(len(df))
    e2e_avg    = float(df['E2E_latency'].mean())
    proc_avg   = float(df['processing_time'].mean())
    net_avg    = float(df['network_delay'].mean())

    tmin = df['time_emit'].min()
    tmax = df['time_reception'].max()
    window = (tmax - tmin) if pd.notnull(tmin) and pd.notnull(tmax) else np.nan
    avg_throughput = (total_msgs / window) if (window and window > 0) else np.nan

    pd.DataFrame({
        'algorithm':[algo],
        'total_messages':[total_msgs],
        'avg_E2E_latency':[e2e_avg],
        'avg_processing_time':[proc_avg],
        'avg_network_delay':[net_avg],
        'tmin_emit':[tmin],
        'tmax_reception':[tmax],
        'window':[window],
        'avg_throughput':[avg_throughput]
    }).to_csv(outdir / 'summary_global.csv', index=False)

    # Per-app
    e2e_per_app = (df.groupby('app')['E2E_latency'].mean()
                     .reset_index().rename(columns={'E2E_latency':'avg_E2E_latency'}))
    e2e_per_app.to_csv(outdir / 'e2e_latency_per_app.csv', index=False)
    e2e_per_app.rename(columns={'avg_E2E_latency':'avg_response_time'}).to_csv(outdir / 'response_time_per_app.csv', index=False)

    # Per-module
    if 'module' in df.columns:
        proc_per_module = (df.groupby(['app','module'])['processing_time']
                             .mean().reset_index().rename(columns={'processing_time':'avg_processing_time'}))
        proc_per_module.to_csv(outdir / 'processing_time_per_module.csv', index=False)

    # Per-link network delay (from end-to-end logs)
    if set(['TOPO.src','TOPO.dst']).issubset(df.columns):
        netdelay_per_link = (df.groupby(['TOPO.src','TOPO.dst'])['network_delay']
                               .mean().reset_index().rename(columns={'network_delay':'avg_network_delay'}))
        netdelay_per_link.to_csv(outdir / 'network_delay_per_link.csv', index=False)

    # Entities-based outputs
    if entities_path:
        ent = load_entities(entities_path)

        coverage = {}
        # Join node types for dst and src if available
        merged = df.copy()
        if 'TOPO.dst' in merged.columns:
            tmp_dst = ent.rename(columns={'id_resource':'TOPO.dst'})
            merged = merged.merge(tmp_dst, on='TOPO.dst', how='left')
            merged = merged.rename(columns={'node_type':'dst_type'})
            coverage['dst_type_nonnull'] = int(merged['dst_type'].notna().sum())
        else:
            merged['dst_type'] = np.nan
            coverage['dst_type_nonnull'] = 0

        if 'TOPO.src' in merged.columns:
            tmp_src = ent.rename(columns={'id_resource':'TOPO.src'})
            merged = merged.merge(tmp_src, on='TOPO.src', how='left')
            merged = merged.rename(columns={'node_type':'src_type'})
            coverage['src_type_nonnull'] = int(merged['src_type'].notna().sum())
        else:
            merged['src_type'] = np.nan
            coverage['src_type_nonnull'] = 0

        coverage['total_rows'] = int(len(merged))
        pd.DataFrame([coverage]).to_csv(outdir / 'entities_coverage_report.csv', index=False)

        # 1) Layer performance (avg E2E by dst_type)
        if merged['dst_type'].notna().any():
            layer_perf = (merged.groupby('dst_type')['E2E_latency']
                            .mean().reset_index().rename(columns={'E2E_latency':'avg_E2E_latency'})
                            .sort_values('avg_E2E_latency'))
            layer_perf.to_csv(outdir / 'layer_performance.csv', index=False)

        # 2) Layer-link summary (avg network_delay by src_type -> dst_type)
        if merged['src_type'].notna().any() and merged['dst_type'].notna().any():
            layer_link = (merged.groupby(['src_type','dst_type'])['network_delay']
                            .mean().reset_index().rename(columns={'network_delay':'avg_network_delay'})
                            .sort_values('avg_network_delay', ascending=False))
            layer_link.to_csv(outdir / 'layer_link_summary.csv', index=False)

    # Throughput series
    if bin_width and bin_width > 0:
        bins = np.floor(df['time_reception'] / bin_width) * bin_width
        thr_bins = (pd.DataFrame({'time_bin': bins})
                      .value_counts().reset_index(name='events')
                      .sort_values('time_bin'))
        thr_bins['throughput_events_per_time'] = thr_bins['events'] / bin_width
        thr_bins.to_csv(outdir / f'throughput_timebins_w{int(bin_width)}.csv', index=False)

    # Overall throughput (duplicate for convenience)
    pd.DataFrame({
        'algorithm':[algo],
        'events':[total_msgs],
        'window':[window],
        'throughput_events_per_time':[avg_throughput]
    }).to_csv(outdir / 'throughput_overall.csv', index=False)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--csv', required=True, help='Path to results_*.csv (end-to-end events)')
    parser.add_argument('--algo', required=True, help='Algorithm label')
    parser.add_argument('--outdir', required=True, help='Output directory')
    parser.add_argument('--bin_width', type=float, default=100.0, help='Time bin width for throughput (default 100)')
    parser.add_argument('--entities', type=str, default=None, help='Optional CSV with columns: id_resource|node_id|id, node_type')
    args = parser.parse_args()
    main(args.csv, args.algo, args.outdir, args.bin_width, args.entities)
