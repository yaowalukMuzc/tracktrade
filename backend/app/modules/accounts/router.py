"""`/accounts` — trading accounts, risk profile, rules, symbol mapping, audit log (F-02, F-03)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import AccessContext
from app.core.db import get_session
from app.modules.accounts import service
from app.modules.accounts.schemas import (
    AccountCreate,
    AccountOut,
    AccountUpdate,
    AuditLogOut,
    RiskProfileIn,
    RiskProfileOut,
    RiskProfileVersionOut,
    RiskStatusOut,
    RuleCreate,
    RuleOut,
    RuleUpdate,
    SymbolOverrideIn,
    SymbolOverrideOut,
    SymbolResolveOut,
)
from app.modules.audit.service import list_for_account
from app.modules.auth.deps import get_access_context

router = APIRouter(prefix="/accounts", tags=["accounts"])

Ctx = Depends(get_access_context)
Db = Depends(get_session)


@router.get("", response_model=list[AccountOut])
async def list_accounts(
    include_archived: bool = Query(False), ctx: AccessContext = Ctx, session: AsyncSession = Db
) -> list[AccountOut]:
    rows = await service.list_accounts(session, ctx, include_archived=include_archived)
    return [AccountOut.model_validate(a) for a in rows]


@router.post("", response_model=AccountOut, status_code=status.HTTP_201_CREATED)
async def create_account(
    body: AccountCreate, ctx: AccessContext = Ctx, session: AsyncSession = Db
) -> AccountOut:
    return AccountOut.model_validate(await service.create_account(session, ctx, body))


@router.get("/{account_id}", response_model=AccountOut)
async def get_account(
    account_id: uuid.UUID, ctx: AccessContext = Ctx, session: AsyncSession = Db
) -> AccountOut:
    return AccountOut.model_validate(await service.get_account(session, ctx, account_id))


@router.patch("/{account_id}", response_model=AccountOut)
async def update_account(
    account_id: uuid.UUID, body: AccountUpdate, ctx: AccessContext = Ctx, session: AsyncSession = Db
) -> AccountOut:
    account = await service.update_account(session, ctx, account_id, body)
    return AccountOut.model_validate(account)


@router.post("/{account_id}/archive", response_model=AccountOut)
async def archive_account(
    account_id: uuid.UUID, ctx: AccessContext = Ctx, session: AsyncSession = Db
) -> AccountOut:
    return AccountOut.model_validate(await service.set_archived(session, ctx, account_id, True))


@router.post("/{account_id}/unarchive", response_model=AccountOut)
async def unarchive_account(
    account_id: uuid.UUID, ctx: AccessContext = Ctx, session: AsyncSession = Db
) -> AccountOut:
    return AccountOut.model_validate(await service.set_archived(session, ctx, account_id, False))


# ------------------------------------------------------------------ risk


@router.get("/{account_id}/risk-profile", response_model=RiskProfileOut)
async def get_risk_profile(
    account_id: uuid.UUID, ctx: AccessContext = Ctx, session: AsyncSession = Db
) -> RiskProfileOut:
    return RiskProfileOut.model_validate(await service.get_risk_profile(session, ctx, account_id))


@router.put("/{account_id}/risk-profile", response_model=RiskProfileOut)
async def put_risk_profile(
    account_id: uuid.UUID, body: RiskProfileIn, ctx: AccessContext = Ctx, session: AsyncSession = Db
) -> RiskProfileOut:
    profile = await service.update_risk_profile(session, ctx, account_id, body)
    return RiskProfileOut.model_validate(profile)


@router.get("/{account_id}/risk-profile/versions", response_model=list[RiskProfileVersionOut])
async def risk_profile_versions(
    account_id: uuid.UUID, ctx: AccessContext = Ctx, session: AsyncSession = Db
) -> list[RiskProfileVersionOut]:
    rows = await service.list_risk_profile_versions(session, ctx, account_id)
    return [RiskProfileVersionOut.model_validate(v) for v in rows]


@router.get("/{account_id}/risk-status", response_model=RiskStatusOut)
async def risk_status(
    account_id: uuid.UUID, ctx: AccessContext = Ctx, session: AsyncSession = Db
) -> RiskStatusOut:
    return await service.risk_status(session, ctx, account_id)


# ------------------------------------------------------------------ rules


@router.get("/{account_id}/rules", response_model=list[RuleOut])
async def list_rules(
    account_id: uuid.UUID, ctx: AccessContext = Ctx, session: AsyncSession = Db
) -> list[RuleOut]:
    return [RuleOut.model_validate(r) for r in await service.list_rules(session, ctx, account_id)]


@router.post("/{account_id}/rules", response_model=RuleOut, status_code=status.HTTP_201_CREATED)
async def create_rule(
    account_id: uuid.UUID, body: RuleCreate, ctx: AccessContext = Ctx, session: AsyncSession = Db
) -> RuleOut:
    return RuleOut.model_validate(await service.create_rule(session, ctx, account_id, body))


@router.patch("/{account_id}/rules/{rule_id}", response_model=RuleOut)
async def update_rule(
    account_id: uuid.UUID,
    rule_id: uuid.UUID,
    body: RuleUpdate,
    ctx: AccessContext = Ctx,
    session: AsyncSession = Db,
) -> RuleOut:
    rule = await service.update_rule(session, ctx, account_id, rule_id, body)
    return RuleOut.model_validate(rule)


@router.delete("/{account_id}/rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_rule(
    account_id: uuid.UUID, rule_id: uuid.UUID, ctx: AccessContext = Ctx, session: AsyncSession = Db
) -> Response:
    await service.delete_rule(session, ctx, account_id, rule_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ------------------------------------------------------------------ symbol mapping


@router.get("/{account_id}/symbol-overrides", response_model=list[SymbolOverrideOut])
async def list_overrides(
    account_id: uuid.UUID, ctx: AccessContext = Ctx, session: AsyncSession = Db
) -> list[SymbolOverrideOut]:
    return await service.list_overrides(session, ctx, account_id)


@router.put("/{account_id}/symbol-overrides", response_model=SymbolOverrideOut)
async def upsert_override(
    account_id: uuid.UUID,
    body: SymbolOverrideIn,
    ctx: AccessContext = Ctx,
    session: AsyncSession = Db,
) -> SymbolOverrideOut:
    return await service.upsert_override(session, ctx, account_id, body)


@router.delete(
    "/{account_id}/symbol-overrides/{override_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_override(
    account_id: uuid.UUID,
    override_id: uuid.UUID,
    ctx: AccessContext = Ctx,
    session: AsyncSession = Db,
) -> Response:
    await service.delete_override(session, ctx, account_id, override_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{account_id}/symbols/resolve", response_model=SymbolResolveOut)
async def resolve_symbol(
    account_id: uuid.UUID,
    broker_symbol: str = Query(min_length=1, max_length=32),
    ctx: AccessContext = Ctx,
    session: AsyncSession = Db,
) -> SymbolResolveOut:
    return await service.resolve_symbol(session, ctx, account_id, broker_symbol)


# ------------------------------------------------------------------ audit


@router.get("/{account_id}/audit-log", response_model=list[AuditLogOut])
async def audit_log(
    account_id: uuid.UUID,
    limit: int = Query(100, ge=1, le=500),
    ctx: AccessContext = Ctx,
    session: AsyncSession = Db,
) -> list[AuditLogOut]:
    await service.get_account(session, ctx, account_id)
    rows = await list_for_account(session, ctx, account_id, limit=limit)
    return [AuditLogOut.model_validate(r) for r in rows]
