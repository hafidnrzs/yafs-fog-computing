def evaluate_simulation(event_log, deadline_ms=None):
    """
    Evaluasi hasil simulasi: latency, deadline miss, throughput, hop count, dll.
    """
    delays = [e.get('total_delay', e.get('delay', 0)) for e in event_log if 'total_delay' in e or 'delay' in e]
    hops = [len(e.get('path', [])) - 1 for e in event_log if 'path' in e and len(e['path']) > 1]
    rates = [e.get('rate', 0) for e in event_log if 'rate' in e]
    total_requests = len(delays)

    if not delays:
        print("No delay data in event_log!")
        return {}

    avg_delay = sum(delays) / total_requests
    min_delay = min(delays)
    max_delay = max(delays)
    std_delay = (sum((d - avg_delay) ** 2 for d in delays) / total_requests) ** 0.5

    avg_hop = sum(hops) / len(hops) if hops else 0
    max_hop = max(hops) if hops else 0
    min_hop = min(hops) if hops else 0

    throughput = sum(rates)  # total request per detik (jika rate per event)

    result = {
        "avg_delay": avg_delay,
        "min_delay": min_delay,
        "max_delay": max_delay,
        "std_delay": std_delay,
        "total_requests": total_requests,
        "avg_hop": avg_hop,
        "min_hop": min_hop,
        "max_hop": max_hop,
        "throughput": throughput
    }

    if deadline_ms is not None:
        missed = sum(1 for d in delays if d > deadline_ms)
        result["deadline_miss"] = missed
        result["deadline_miss_rate"] = missed / total_requests

    return result