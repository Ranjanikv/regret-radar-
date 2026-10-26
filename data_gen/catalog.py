"""Catalog generation for Products and Stores with size-risk properties."""

import numpy as np
import pandas as pd

from data_gen.config import CATEGORIES, HIGH_RETURN_SIZES, INDIAN_CITIES, SIZES

PRODUCT_NOUNS = {
    "Ethnic Wear": ["Kurta", "Sherwani", "Lehenga", "Anarkali", "Dupatta", "Saree"],
    "Western Wear": ["Slim Denim", "Cotton Shirt", "Blazer", "Chino", "Polo T-Shirt"],
    "Footwear": ["Leather Loafer", "Running Shoes", "Sneaker", "Mojari", "Formal Shoes"],
    "Home & Living": ["Bedsheet Set", "Cushion Cover", "Curtain Pair", "Table Runner"],
    "Beauty & Grooming": ["Moisturizer", "Perfume EDP", "Face Serum", "Hair Oil"],
    "Fashion Accessories": ["Leather Belt", "Silk Tie", "Wallet", "Polarized Sunglasses"],
}


def generate_products(n: int, rng: np.random.Generator) -> pd.DataFrame:
    """Generate product master catalog with MRP, cost price, and category return risks."""
    cat_choices = rng.choice(CATEGORIES, size=n, p=[0.25, 0.25, 0.20, 0.10, 0.10, 0.10])
    size_choices = rng.choice(SIZES, size=n)

    cost_prices = np.zeros(n, dtype=int)
    mrps = np.zeros(n, dtype=int)
    base_return_risks = np.zeros(n, dtype=float)
    product_names = []

    for i in range(n):
        cat = cat_choices[i]
        size = size_choices[i]
        noun = rng.choice(PRODUCT_NOUNS[cat])
        product_names.append(f"{cat.split()[0]} {noun} - {size}")

        if cat in ["Ethnic Wear", "Western Wear", "Footwear"]:
            cost = rng.integers(600, 3500)
            mrp = int(cost * rng.uniform(1.6, 2.4))
            # Higher return probability on apparel/footwear, extreme sizes
            risk = 0.14 if size not in HIGH_RETURN_SIZES else 0.28
        else:
            cost = rng.integers(250, 1800)
            mrp = int(cost * rng.uniform(1.4, 2.0))
            risk = 0.05

        cost_prices[i] = cost
        mrps[i] = mrp
        base_return_risks[i] = round(risk, 3)

    return pd.DataFrame({
        "sku_id": [f"SKU_{i:05d}" for i in range(1, n + 1)],
        "product_name": product_names,
        "category": cat_choices,
        "size": size_choices,
        "cost_price_inr": cost_prices,
        "mrp_inr": mrps,
        "base_return_risk": base_return_risks,
    })


def generate_stores(n: int, rng: np.random.Generator) -> pd.DataFrame:
    """Generate physical and fulfillment store locations across Indian tier-1/tier-2 hubs."""
    store_types = ["Flagship Store", "Mall Store", "High-Street Store", "Fulfillment Hub"]
    city_indices = rng.integers(0, len(INDIAN_CITIES), size=n)

    store_names = []
    cities = []
    states = []
    types = []

    for i in range(n):
        c, s, _ = INDIAN_CITIES[city_indices[i]]
        st = rng.choice(store_types)
        store_names.append(f"RegretRadar {c} {st.split()[0]} #{i + 1}")
        cities.append(c)
        states.append(s)
        types.append(st)

    return pd.DataFrame({
        "store_id": [f"STR_{i:04d}" for i in range(1, n + 1)],
        "store_name": store_names,
        "city": cities,
        "state": states,
        "channel_type": types,
    })
