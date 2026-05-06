def compute_priority(urgency: int, criticality: int, estimated_amount: float) -> float:
    amount_score = 1
    if estimated_amount >= 10000:
        amount_score = 4
    elif estimated_amount >= 5000:
        amount_score = 3
    elif estimated_amount >= 1000:
        amount_score = 2
    raw_score = (urgency * 0.4) + (criticality * 0.4) + (amount_score * 0.2)
    return round(raw_score * 25, 1)
