def review_router(state):

    review = state["review"]

    if review.overall_score >= state["acceptance_score"]:
        state["final_status"] = "accepted"
        return "accept"

    if state["repair_attempts"] >= 5:
        state["final_status"] = "max_repairs_reached"
        return "accept"

    state["final_status"] = "repairing"
    return "repair"