"""Configuration, constants, and scale definitions for synthetic data generation."""

from dataclasses import dataclass
from datetime import date
from typing import Dict, List


@dataclass(frozen=True)
class ScaleConfig:
    """Scale configuration for synthetic dataset generation."""

    num_customers: int
    num_products: int
    num_stores: int
    num_orders: int
    num_days: int
    chunk_size: int = 50_000


SCALES: Dict[str, ScaleConfig] = {
    "small": ScaleConfig(
        num_customers=5_000,
        num_products=250,
        num_stores=15,
        num_orders=50_000,
        num_days=90,
        chunk_size=25_000,
    ),
    "medium": ScaleConfig(
        num_customers=150_000,
        num_products=1_500,
        num_stores=80,
        num_orders=2_000_000,
        num_days=180,
        chunk_size=100_000,
    ),
    "large": ScaleConfig(
        num_customers=1_500_000,
        num_products=5_000,
        num_stores=250,
        num_orders=20_000_000,
        num_days=365,
        chunk_size=250_000,
    ),
}

START_DATE = date(2025, 1, 1)

CATEGORIES: List[str] = [
    "Ethnic Wear",
    "Western Wear",
    "Footwear",
    "Home & Living",
    "Beauty & Grooming",
    "Fashion Accessories",
]

SIZES: List[str] = ["XS", "S", "M", "L", "XL", "XXL", "Free-Size"]

HIGH_RETURN_SIZES: set[str] = {"XS", "XXL"}

CHANNELS: List[str] = ["Web", "App", "POS", "Marketplace"]

RETURN_REASONS: List[str] = [
    "Size too small",
    "Size too large",
    "Fabric quality poor",
    "Color mismatch with image",
    "Defective item",
    "Late delivery",
    "Buyer regret / changed mind",
]

INDIAN_CITIES = [
    ("Mumbai", "Maharashtra", "400001"),
    ("Delhi", "Delhi", "110001"),
    ("Bengaluru", "Karnataka", "560001"),
    ("Hyderabad", "Telangana", "500001"),
    ("Ahmedabad", "Gujarat", "380001"),
    ("Chennai", "Tamil Nadu", "600001"),
    ("Kolkata", "West Bengal", "700001"),
    ("Pune", "Maharashtra", "411001"),
    ("Jaipur", "Rajasthan", "302001"),
    ("Lucknow", "Uttar Pradesh", "226001"),
]
