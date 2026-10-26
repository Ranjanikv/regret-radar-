"""Template-based support ticket generator with churn phrase banks and ground truth labels."""

from datetime import timedelta
from typing import List, Tuple

import numpy as np
import pandas as pd

from data_gen.config import START_DATE

CHURN_PHRASES: List[str] = [
    "I am never shopping here again",
    "Please close my account immediately",
    "Escalating this fraud to consumer court",
    "Terrible customer service, cancelling my loyalty membership",
    "Refund delayed for 3 weeks, completely unacceptable",
    "Worst delivery experience ever, take this back",
    "Switching to your competitor permanently",
    "You ruined my anniversary order, absolute regret",
]

NEUTRAL_PHRASES: List[str] = [
    "Where is my package? Need delivery update.",
    "Can I change the delivery address for my current order?",
    "Need tax invoice copy for expense filing.",
    "How do I redeem my loyalty reward points on app?",
    "Inquiring if this item will restock in size Large soon.",
]

POSITIVE_PHRASES: List[str] = [
    "Fast delivery and great packaging, thank you!",
    "Appreciated the prompt size replacement at the store.",
    "Excellent quality fabric, will recommend to friends.",
]


def generate_support_tickets(
    df_customers: pd.DataFrame,
    df_returns: pd.DataFrame,
    num_days: int,
    rng: np.random.Generator,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Generate template-based support tickets and correlated ground-truth churn labels."""
    cust_ids = df_customers["customer_id"].to_numpy()
    ret_cust_set = set(df_returns["customer_id"].unique()) if not df_returns.empty else set()

    tickets = []
    t_id = 1

    # High-risk cohort from returns + random subset
    churn_flagged_cust = set()

    for cid in cust_ids:
        has_returns = cid in ret_cust_set
        # Prob of creating tickets
        p_ticket = 0.55 if has_returns else 0.12
        if rng.random() > p_ticket:
            continue

        num_tix = rng.integers(1, 4) if has_returns else 1
        for _ in range(num_tix):
            t_day = rng.integers(10, num_days)
            t_date = START_DATE + timedelta(days=int(t_day))

            if has_returns and rng.random() < 0.65:
                phrase = rng.choice(CHURN_PHRASES)
                subject = "Refund Delay / Dissatisfaction Escalation"
                sentiment = "Negative"
                churn_flag = 1
                churn_flagged_cust.add(cid)
            elif rng.random() < 0.20:
                phrase = rng.choice(POSITIVE_PHRASES)
                subject = "Order Feedback / Compliment"
                sentiment = "Positive"
                churn_flag = 0
            else:
                phrase = rng.choice(NEUTRAL_PHRASES)
                subject = "Order Status / Inquiry"
                sentiment = "Neutral"
                churn_flag = 0

            ref_id = rng.integers(1000, 9999)
            text = f"Customer Query regarding order: {phrase} Reference ID: REF-{ref_id}."
            tickets.append({
                "ticket_id": f"TCK_{t_id:08d}",
                "customer_id": cid,
                "created_at": t_date,
                "subject": subject,
                "ticket_text": text,
                "sentiment": sentiment,
                "churn_intent_flag": churn_flag,
            })
            t_id += 1

    df_tickets = pd.DataFrame(tickets)

    # Churn labels: flagged customers have 78% churn rate, others 4%
    churn_labels = []
    for cid in cust_ids:
        is_high_risk = cid in churn_flagged_cust
        churn_prob = 0.78 if is_high_risk else 0.04
        churned = 1 if rng.random() < churn_prob else 0
        extra_days = int(rng.integers(60, num_days + 30))
        churn_date = START_DATE + timedelta(days=extra_days) if churned else None
        risk_score = (
            round(rng.uniform(0.70, 0.98), 2)
            if is_high_risk
            else round(rng.uniform(0.01, 0.25), 2)
        )

        churn_labels.append({
            "customer_id": cid,
            "churned": churned,
            "churn_date": churn_date,
            "churn_risk_score": risk_score,
            "is_high_risk_cohort": 1 if is_high_risk else 0,
        })

    df_churn = pd.DataFrame(churn_labels)
    return df_tickets, df_churn
