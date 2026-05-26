"""
Realistic seed data generator for Multi-Agent RevOps Orchestrator demo.

Creates:
- 10 Indian automotive / industrial dealers across 4 regions
- 6 months of monthly revenue history (Oct 2024 - Mar 2025)
- 3 competitor pricing signals (used by Analyst)

Run via: python -m src.database.seed_data
"""

from __future__ import annotations

import logging
import random
import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from src.database.connection import db_session, init_db
from src.database.models import Dealer, RevenueRecord, CompetitorSignal

logger = logging.getLogger(__name__)


# =============================================================================
# Seed Configuration - Realistic Indian B2B Industrial/Auto Dealers
# =============================================================================

DEALERS = [
    {
        "dealer_code": "DLR-NORTH-001",
        "name": "North India Heavy Equipment Pvt Ltd",
        "region": "North",
        "city": "Gurgaon",
        "state": "Haryana",
        "tier": "A",
        "contact_email": "procurement@northindiaheavy.in",
        "contact_phone": "+919810012345",
    },
    {
        "dealer_code": "DLR-NORTH-002",
        "name": "Punjab Industrial Supplies",
        "region": "North",
        "city": "Ludhiana",
        "state": "Punjab",
        "tier": "B",
        "contact_email": "ops@punjabindustrials.in",
    },
    {
        "dealer_code": "DLR-WEST-001",
        "name": "Maharashtra Construction Equipment",
        "region": "West",
        "city": "Pune",
        "state": "Maharashtra",
        "tier": "A",
        "contact_email": "sales@maharashtraconst.in",
        "contact_phone": "+919822334455",
    },
    {
        "dealer_code": "DLR-WEST-002",
        "name": "Gujarat Earthmovers Distributors",
        "region": "West",
        "city": "Ahmedabad",
        "state": "Gujarat",
        "tier": "B",
        "contact_email": "info@gujaratearthmovers.com",
    },
    {
        "dealer_code": "DLR-SOUTH-001",
        "name": "Karnataka Mining Solutions",
        "region": "South",
        "city": "Bangalore",
        "state": "Karnataka",
        "tier": "A",
        "contact_email": "fleet@karnatakamining.in",
    },
    {
        "dealer_code": "DLR-SOUTH-002",
        "name": "Tamil Nadu Heavy Machinery",
        "region": "South",
        "city": "Chennai",
        "state": "Tamil Nadu",
        "tier": "B",
        "contact_email": "purchase@tnheavymach.in",
    },
    {
        "dealer_code": "DLR-SOUTH-003",
        "name": "Hyderabad Infra Equipment",
        "region": "South",
        "city": "Hyderabad",
        "state": "Telangana",
        "tier": "C",
        "contact_email": "admin@hyderabadinfra.com",
    },
    {
        "dealer_code": "DLR-EAST-001",
        "name": "Bengal Industrial Distributors",
        "region": "East",
        "city": "Kolkata",
        "state": "West Bengal",
        "tier": "B",
        "contact_email": "contact@bengalindustrial.in",
    },
    {
        "dealer_code": "DLR-EAST-002",
        "name": "Odisha Mining Partners",
        "region": "East",
        "city": "Bhubaneswar",
        "state": "Odisha",
        "tier": "C",
        "contact_email": "ops@odishamining.co.in",
    },
    {
        "dealer_code": "DLR-NORTH-003",
        "name": "Delhi NCR Equipment Rentals",
        "region": "North",
        "city": "Noida",
        "state": "Uttar Pradesh",
        "tier": "A",
        "contact_email": "fleet@delhincrental.in",
        "contact_phone": "+919873334455",
    },
]

# Base monthly revenue targets (INR) - realistic for mid-size industrial dealers
BASE_REVENUES = {
    "DLR-NORTH-001": 18500000,
    "DLR-NORTH-002": 9200000,
    "DLR-WEST-001": 15700000,
    "DLR-WEST-002": 7800000,
    "DLR-SOUTH-001": 21300000,
    "DLR-SOUTH-002": 11400000,
    "DLR-SOUTH-003": 5100000,
    "DLR-EAST-001": 8900000,
    "DLR-EAST-002": 4300000,
    "DLR-NORTH-003": 16200000,
}

COMPETITOR_SIGNALS = [
    {
        "source_url": "https://www.example.com/competitor-a-price-update-march2025",
        "competitor_name": "Competitor A (Tata Hitachi)",
        "signal_type": "pricing",
        "title": "Tata Hitachi announces 4.5% price hike on EX-200 series excavators effective April 2025",
        "summary": "Major competitor increased list price on 20-ton excavators by 4.5%. Dealer margin pressure expected to rise 120-180 bps.",
        "extracted_data": {
            "price_change_pct": 4.5,
            "product_line": "EX-200 Series",
            "effective_date": "2025-04-01",
            "impact": "margin_pressure",
        },
        "relevance_score": 0.92,
    },
    {
        "source_url": "https://economictimes.indiatimes.com/industry/transportation/railways/railway-ministry-approves-12000-cr-order",
        "competitor_name": "Competitor B (BEML)",
        "signal_type": "news",
        "title": "BEML wins ₹12,000 Cr railway order - may reduce focus on private construction segment",
        "summary": "BEML (state-owned) wins massive Indian Railways contract. Industry analysts expect 15-20% reduction in private dealer push in Q2-Q3 2025.",
        "extracted_data": {
            "contract_value_cr": 12000,
            "segment_shift": "private_to_govt",
            "expected_impact": "reduced_competition_in_private_segment",
        },
        "relevance_score": 0.78,
    },
    {
        "source_url": "https://www.example.com/competitor-c-dealer-expansion",
        "competitor_name": "Competitor C (JCB India)",
        "signal_type": "dealer_activity",
        "title": "JCB India appoints 3 new dealers in Karnataka & Telangana - aggressive expansion",
        "summary": "JCB is expanding its footprint in South India with 3 new dealerships. Direct competitive threat to our Karnataka and Hyderabad dealers.",
        "extracted_data": {
            "new_dealers": 3,
            "regions": ["Karnataka", "Telangana"],
            "threat_level": "high",
        },
        "relevance_score": 0.85,
    },
]


def generate_revenue_history(dealer_code: str, months: int = 6) -> list[dict]:
    """Generate 6 months of realistic revenue data with seasonality and variance."""
    base = BASE_REVENUES[dealer_code]
    records = []
    today = date(2025, 3, 1)  # Latest period in demo

    for i in range(months):
        period = date(today.year, today.month, 1) - timedelta(days=32 * i)
        period = period.replace(day=1)

        # Seasonality: Q4 (Oct-Dec) stronger for construction, Q1 softer
        month = period.month
        seasonal_factor = 1.0
        if month in [10, 11, 12]:
            seasonal_factor = 1.18
        elif month in [1, 2, 3]:
            seasonal_factor = 0.87

        # Random variance ±12%
        variance = random.uniform(0.88, 1.12)
        revenue = round(base * seasonal_factor * variance, 0)

        # Target is usually 8-12% above previous year average
        target = round(base * 1.09 * seasonal_factor, 0)

        units = int(revenue / random.choice([185000, 210000, 245000]))  # avg selling price variance

        # MoM growth (simulated)
        growth = round(random.uniform(-9.5, 14.2), 1)

        records.append({
            "period": period,
            "revenue_inr": revenue,
            "units_sold": units,
            "target_inr": target,
            "growth_pct": growth,
        })

    return sorted(records, key=lambda x: x["period"])


def seed_dealers(db: Session) -> list[Dealer]:
    """Insert 10 dealers."""
    dealers = []
    for d in DEALERS:
        dealer = Dealer(
            dealer_code=d["dealer_code"],
            name=d["name"],
            region=d["region"],
            city=d["city"],
            state=d["state"],
            tier=d["tier"],
            contact_email=d.get("contact_email"),
            contact_phone=d.get("contact_phone"),
            is_active=True,
        )
        db.add(dealer)
        dealers.append(dealer)

    db.flush()
    logger.info(f"Seeded {len(dealers)} dealers")
    return dealers


def seed_revenue_records(db: Session, dealers: list[Dealer]) -> int:
    """Insert 6 months of revenue for every dealer."""
    count = 0
    dealer_map = {d.dealer_code: d.id for d in dealers}

    for dealer_code, dealer_id in dealer_map.items():
        history = generate_revenue_history(dealer_code)
        for rec in history:
            revenue_record = RevenueRecord(
                dealer_id=dealer_id,
                period=rec["period"],
                revenue_inr=rec["revenue_inr"],
                units_sold=rec["units_sold"],
                target_inr=rec["target_inr"],
                growth_pct=rec["growth_pct"],
            )
            db.add(revenue_record)
            count += 1

    db.flush()
    logger.info(f"Seeded {count} revenue records (6 months × 10 dealers)")
    return count


def seed_competitor_signals(db: Session, run_id: uuid.UUID | None = None) -> int:
    """Insert 3 high-quality competitor signals for the demo."""
    count = 0
    for sig in COMPETITOR_SIGNALS:
        signal = CompetitorSignal(
            source_url=sig["source_url"],
            competitor_name=sig["competitor_name"],
            signal_type=sig["signal_type"],
            title=sig["title"],
            summary=sig["summary"],
            extracted_data=sig["extracted_data"],
            relevance_score=sig["relevance_score"],
            detected_at=datetime.utcnow(),
            run_id=run_id,
        )
        db.add(signal)
        count += 1

    db.flush()
    logger.info(f"Seeded {count} competitor signals")
    return count


def seed_all(reset: bool = False) -> None:
    """
    Main entry point. Seeds the complete demo dataset.
    Call this after docker-compose up or in CI for integration tests.
    """
    if reset:
        from src.database.connection import reset_db
        reset_db()
    else:
        init_db()

    with db_session() as db:
        # Idempotency: only seed if no dealers exist
        existing = db.query(Dealer).count()
        if existing > 0:
            logger.info(f"Database already contains {existing} dealers. Skipping seed.")
            return

        dealers = seed_dealers(db)
        revenue_count = seed_revenue_records(db, dealers)
        signal_count = seed_competitor_signals(db)

        logger.info(
            f"✅ Seed complete: {len(dealers)} dealers, {revenue_count} revenue records, "
            f"{signal_count} competitor signals"
        )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("🌱 Seeding RevOps demo database...")
    seed_all(reset=False)
    print("Done.")
