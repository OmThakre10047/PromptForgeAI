def add_trace(state, result):
    state["trace"].append(
        {
            "agent": result.agent,
            "model": result.model,
            "latency": result.latency,
        }
    )