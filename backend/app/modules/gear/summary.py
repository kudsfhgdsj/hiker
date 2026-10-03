"""Totals of a user's gear: count, weight and purchase value, optionally per group."""

from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.auth.models import User
from app.modules.gear.models import GearItem, GearType
from app.modules.gear.schemas import GearSummaryGroup, GearSummaryOut, GearTotals, MoneyTotal
from app.modules.gear.service import ItemFilter, item_conditions


def _totals(items: list[GearItem]) -> dict:
    value: dict[str, float] = defaultdict(float)
    for item in items:
        if item.purchase_price is not None and item.currency:
            value[item.currency] += item.purchase_price
    return {
        "item_count": len(items),
        "weight_g": sum(item.weight_g or 0 for item in items),
        "items_without_weight": sum(item.weight_g is None for item in items),
        # Prices in different currencies are never added up.
        "value": [
            MoneyTotal(currency=currency, amount=round(amount, 2))
            for currency, amount in sorted(value.items())
        ],
        "items_without_price": sum(item.purchase_price is None for item in items),
    }


def _group_keys(item: GearItem, group_by: str, type_names: dict) -> list[tuple[str | None, str]]:
    """The groups an item belongs to, as (key, label); key None = not assigned."""
    if group_by == "tag":
        return [(str(tag.id), tag.name) for tag in item.tags] or [(None, None)]
    if group_by == "type":
        if item.type_id is None:
            return [(None, None)]
        return [(str(item.type_id), type_names.get(item.type_id))]
    value = item.status if group_by == "status" else item.brand
    return [(value, value)]


def summarize(db: Session, user: User, filters: ItemFilter, group_by: str | None) -> GearSummaryOut:
    items = list(db.scalars(select(GearItem).where(*item_conditions(user, filters))))
    groups: list[GearSummaryGroup] = []
    if group_by is not None:
        type_names = dict(db.execute(select(GearType.id, GearType.name)).all())
        members: dict[tuple, list[GearItem]] = defaultdict(list)
        for item in items:
            for key in _group_keys(item, group_by, type_names):
                members[key].append(item)
        # Sorted by label, the group of unassigned items last.
        ordered = sorted(members, key=lambda key: (key[0] is None, (key[1] or "").lower()))
        groups = [
            GearSummaryGroup(key=key, label=label, **_totals(members[key, label]))
            for key, label in ordered
        ]
    return GearSummaryOut(group_by=group_by, total=GearTotals(**_totals(items)), groups=groups)
