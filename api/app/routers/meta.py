"""Metadata / value-set routes. Powers the expense-sheet form dropdowns (expense types and
supported currencies) so the client populates them from one source of truth (change req)."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.auth.dependencies import current_principal
from app.principal import Principal
from app.schemas.dto import ValueSetsOut
from app.value_sets import EXPENSE_TYPES, SUPPORTED_CURRENCIES

router = APIRouter(
    prefix="/meta",
    tags=["meta"],
    responses={401: {"description": "Missing or invalid bearer token"}},
)


@router.get("/value-sets", response_model=ValueSetsOut, summary="Expense types + supported currencies")
async def value_sets(_: Principal = Depends(current_principal)) -> ValueSetsOut:
    """The fixed value sets for the line-item form. `expense_types` includes **Other**, which
    on the client reveals a free-text field stored as `expense_type_other`."""
    return ValueSetsOut(expense_types=EXPENSE_TYPES, currencies=list(SUPPORTED_CURRENCIES))
