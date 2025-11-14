
"""
extract_alloc_definition.py
---------------------------
Extract useful summaries from a single YAFS allocDefinition JSON file
(e.g., allocDefinitionILP.json, allocDefinitionGA.json).

Outputs (written to --outdir):
- allocation.csv                  (app, module_name, id_resource)
- per_node_service_counts.csv     (node_id, service_count)
- per_app_service_counts.csv      (app, service_count)
- per_module_replication.csv      (app, module_name, replica_count, unique_nodes)
- summary.csv                     (total_services, unique_nodes, [cloud/fog counts & ratios if --cloud_node_id])
- ratios.csv                      (fog_ratio, cloud_ratio, total_services, cloud_node_id)  # only if --cloud_node_id

Usage:
  python extract_alloc_definition.py \\
    --json /path/to/allocDefinitionILP.json \\
    --outdir /path/to/outdir \\
    [--cloud_node_id 100]
"""

import argparse
import json
from pathlib import Path
import pandas as pd
import numpy as np
from typing import Optional

def main(json_path: str, outdir: str, cloud_node_id: Optional[int] = None):
    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)

    with open(json_path, "r") as f:
        data = json.load(f)

    if not isinstance(data, dict) or "initialAllocation" not in data:
        raise ValueError("Input JSON must be an allocDefinition-like dict with 'initialAllocation' list.")

    alloc = pd.DataFrame(data["initialAllocation"])
    # normalize column names and types
    ren = {"id_resource":"id_resource", "app":"app", "module_name":"module_name"}
    alloc = alloc.rename(columns=ren)
    for c in ["app","id_resource"]:
        if c in alloc.columns:
            alloc[c] = pd.to_numeric(alloc[c], errors="coerce")
    if "module_name" not in alloc.columns:
        # Fallback: try 'module' key
        if "module" in alloc.columns:
            alloc = alloc.rename(columns={"module":"module_name"})
        else:
            alloc["module_name"] = alloc.get("module_name", "unknown")

    # Save raw allocation
    alloc[["app","module_name","id_resource"]].to_csv(out / "allocation.csv", index=False)

    # Per-node counts
    per_node = (alloc["id_resource"]
                .value_counts().sort_index()
                .rename("service_count").to_frame())
    per_node.index.name = "node_id"
    per_node = per_node.reset_index()
    per_node.to_csv(out / "per_node_service_counts.csv", index=False)

    # Per-app counts
    per_app = (alloc["app"]
               .value_counts().sort_index()
               .rename("service_count").to_frame())
    per_app.index.name = "app"
    per_app = per_app.reset_index()
    per_app.to_csv(out / "per_app_service_counts.csv", index=False)

    # Per-module replication across nodes
    rep = (alloc.groupby(["app","module_name"])["id_resource"]
                 .agg(unique_nodes=lambda s: sorted(pd.Series(s).dropna().unique().tolist()),
                      replica_count=lambda s: pd.Series(s).nunique())
                 .reset_index())
    # Flatten unique_nodes as concise string
    rep["unique_nodes"] = rep["unique_nodes"].apply(lambda x: ",".join(map(str, x)))
    rep = rep[["app","module_name","replica_count","unique_nodes"]]
    rep.to_csv(out / "per_module_replication.csv", index=False)

    # Summary & ratios
    total_services = int(len(alloc))
    unique_nodes = int(alloc["id_resource"].nunique())
    summary = {
        "total_services": total_services,
        "unique_nodes": unique_nodes,
    }

    if cloud_node_id is not None:
        cloud_services = int(per_node.loc[per_node["node_id"] == cloud_node_id, "service_count"].sum())
        fog_services = total_services - cloud_services
        fog_ratio = (fog_services / total_services) if total_services else np.nan
        cloud_ratio = (cloud_services / total_services) if total_services else np.nan
        summary.update({
            "cloud_node_id": cloud_node_id,
            "cloud_services": cloud_services,
            "fog_services": fog_services,
            "fog_ratio": fog_ratio,
            "cloud_ratio": cloud_ratio,
        })
        pd.DataFrame({
            "fog_ratio":[fog_ratio],
            "cloud_ratio":[cloud_ratio],
            "total_services":[total_services],
            "cloud_node_id":[cloud_node_id],
        }).to_csv(out / "ratios.csv", index=False)

    pd.DataFrame([summary]).to_csv(out / "summary.csv", index=False)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", required=True, help="Path to allocDefinition*.json")
    parser.add_argument("--outdir", required=True, help="Directory to write outputs")
    parser.add_argument("--cloud_node_id", type=int, default=None, help="Cloud node id (optional)")
    args = parser.parse_args()
    main(args.json, args.outdir, args.cloud_node_id)
