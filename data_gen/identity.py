"""Vectorized generator for ground truth customers and fragmented channel identities."""

from typing import Tuple

import numpy as np
import pandas as pd

from data_gen.config import INDIAN_CITIES

FIRST_NAMES = [
    "Aarav", "Vivaan", "Aditya", "Vihaan", "Arjun", "Sai", "Reyansh", "Ayaan",
    "Krishna", "Ishaan", "Shaurya", "Atharva", "Ananya", "Diya", "Saanvi", "Aadhya",
    "Pari", "Chiara", "Myra", "Riya", "Isha", "Kavya", "Navya", "Aditi",
    "Rohan", "Pooja", "Vikram", "Sneha", "Rahul", "Priya", "Amit", "Neha",
]

LAST_NAMES = [
    "Sharma", "Verma", "Patel", "Mehta", "Iyer", "Nair", "Reddy", "Rao",
    "Kulkarni", "Deshmukh", "Mukherjee", "Chatterjee", "Gupta", "Agarwal",
    "Singh", "Chauhan", "Bose", "Ghosh", "Joshi", "Bhat", "Kapoor", "Khan",
]

DOMAINS = ["gmail.com", "yahoo.co.in", "outlook.com", "icloud.com", "rediffmail.com"]


def _inject_typo(series: pd.Series, rng: np.random.Generator, prob: float = 0.25) -> pd.Series:
    """Vectorized-style substitution to inject realistic spelling typos into names."""
    names = series.to_numpy(dtype=object).copy()
    mask = rng.random(len(names)) < prob
    for i in np.flatnonzero(mask):
        val = str(names[i])
        if len(val) > 4:
            idx = rng.integers(1, len(val) - 1)
            # Swap or double char
            if rng.random() < 0.5:
                val = val[:idx] + val[idx] + val[idx:]
            else:
                val = val[:idx] + val[idx + 1:]
            names[i] = val
    return pd.Series(names, index=series.index)


def generate_customers_true(n: int, rng: np.random.Generator) -> pd.DataFrame:
    """Generate ground-truth master customer directory."""
    fn_idx = rng.integers(0, len(FIRST_NAMES), size=n)
    ln_idx = rng.integers(0, len(LAST_NAMES), size=n)
    first_names = np.array(FIRST_NAMES)[fn_idx]
    last_names = np.array(LAST_NAMES)[ln_idx]

    city_idx = rng.integers(0, len(INDIAN_CITIES), size=n)
    cities = [INDIAN_CITIES[i][0] for i in city_idx]
    states = [INDIAN_CITIES[i][1] for i in city_idx]
    pincodes = [INDIAN_CITIES[i][2] for i in city_idx]

    domain_idx = rng.integers(0, len(DOMAINS), size=n)
    domains = np.array(DOMAINS)[domain_idx]

    cust_ids = [f"CUST_{i:07d}" for i in range(1, n + 1)]
    emails = [
        f"{fn.lower()}.{ln.lower()}{i % 997}@{dom}"
        for i, (fn, ln, dom) in enumerate(zip(first_names, last_names, domains, strict=False))
    ]
    phones = [f"+9198{rng.integers(10000000, 99999999)}" for _ in range(n)]

    return pd.DataFrame({
        "customer_id": cust_ids,
        "first_name": first_names,
        "last_name": last_names,
        "email": emails,
        "phone": phones,
        "city": cities,
        "state": states,
        "pincode": pincodes,
    })


def generate_channel_identities(
    df_true: pd.DataFrame, rng: np.random.Generator
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Generate 4 fragmented touchpoint identities (Web, App, POS, Marketplace) with noise."""
    n = len(df_true)
    c_ids = df_true["customer_id"].to_numpy()

    # 1. Web Users (coverage ~70%)
    web_mask = rng.random(n) < 0.70
    web_cust = c_ids[web_mask]
    web_names = _inject_typo(df_true.loc[web_mask, "first_name"], rng, 0.15)
    web_last = df_true.loc[web_mask, "last_name"].to_numpy()
    df_web = pd.DataFrame({
        "web_user_id": [f"WEB_{i:07d}" for i in range(1, len(web_cust) + 1)],
        "customer_id": web_cust,
        "email": df_true.loc[web_mask, "email"].to_numpy(),
        "phone": df_true.loc[web_mask, "phone"].to_numpy(),
        "full_name": [f"{fn} {ln}" for fn, ln in zip(web_names, web_last, strict=False)],
        "cookie_id": [f"ck_{rng.integers(10000000, 99999999)}" for _ in range(len(web_cust))],
    })

    # 2. App Users (coverage ~60%)
    app_mask = rng.random(n) < 0.60
    app_cust = c_ids[app_mask]
    app_first = df_true.loc[app_mask, "first_name"].to_numpy()
    app_last = _inject_typo(df_true.loc[app_mask, "last_name"], rng, 0.20)
    # Phones with format variation (e.g. without +91)
    raw_phones = [p.replace("+91", "") for p in df_true.loc[app_mask, "phone"]]
    df_app = pd.DataFrame({
        "app_user_id": [f"APP_{i:07d}" for i in range(1, len(app_cust) + 1)],
        "customer_id": app_cust,
        "device_id": [f"dev_{rng.integers(1000000, 9999999)}" for _ in range(len(app_cust))],
        "phone_normalized": raw_phones,
        "user_name": [f"{fn} {ln}" for fn, ln in zip(app_first, app_last, strict=False)],
    })

    # 3. POS Loyalty (coverage ~45%)
    pos_mask = rng.random(n) < 0.45
    pos_cust = c_ids[pos_mask]
    pos_phone = df_true.loc[pos_mask, "phone"].to_numpy()
    # 5% phone typos in POS
    pos_phone_noisy = [
        p[:-1] + str(rng.integers(0, 9)) if rng.random() < 0.05 else p for p in pos_phone
    ]
    df_pos = pd.DataFrame({
        "loyalty_card_no": [f"LOY_{i:07d}" for i in range(1, len(pos_cust) + 1)],
        "customer_id": pos_cust,
        "member_name": [
            f"{fn} {ln}"
            for fn, ln in zip(
                df_true.loc[pos_mask, "first_name"],
                df_true.loc[pos_mask, "last_name"],
                strict=False,
            )
        ],
        "registered_phone": pos_phone_noisy,
        "pincode": df_true.loc[pos_mask, "pincode"].to_numpy(),
    })

    # 4. Marketplace Buyers (coverage ~50%)
    mkt_mask = rng.random(n) < 0.50
    mkt_cust = c_ids[mkt_mask]
    platforms = rng.choice(["Amazon.in", "Flipkart", "Myntra", "TataCliq"], size=len(mkt_cust))
    mkt_alias = _inject_typo(df_true.loc[mkt_mask, "first_name"], rng, 0.35)
    # Masked phones: +9198XXXX1234
    mkt_masked_phone = [f"+9198XXXX{p[-4:]}" for p in df_true.loc[mkt_mask, "phone"]]
    df_mkt = pd.DataFrame({
        "marketplace_buyer_id": [f"MKT_{i:07d}" for i in range(1, len(mkt_cust) + 1)],
        "customer_id": mkt_cust,
        "platform": platforms,
        "buyer_alias": mkt_alias.to_numpy(),
        "masked_phone": mkt_masked_phone,
        "shipping_pincode": df_true.loc[mkt_mask, "pincode"].to_numpy(),
    })

    return df_web, df_app, df_pos, df_mkt
