"""Technical debt: shortcuts each system took on purpose, and the plan to fix them.

The same fields as docs/technical_debt.md. Everyone signed in can read them (peers
learn from them, leaders plan with them); the system's editors keep them.
"""
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app import leak_scan
from app import systems_service as svc
from app.auth import current_person
from app.db import get_db
from app.enums import DEBT_CLOSED
from app.leak_guard import LeakGuard
from app.models import Person, System, SystemRole, TechDebt, utcnow
from app.schemas import TechDebtIn

router = APIRouter(prefix="/api", tags=["tech debt"])

RISK_ORDER = {"High": 0, "Medium": 1, "Low": 2}


def overdue(debt: TechDebt, today: Optional[date] = None) -> bool:
    return (debt.status not in DEBT_CLOSED and debt.target_date is not None
            and debt.target_date < (today or date.today()))


def debt_json(d: TechDebt, show=lambda t: t) -> dict:
    return {
        "id": d.id, "title": show(d.title), "description": show(d.description), "reason": show(d.reason),
        "impact": show(d.impact), "fix_plan": show(d.fix_plan), "risk": d.risk, "effort": d.effort,
        "target_date": d.target_date.isoformat() if d.target_date else None,
        "issue_url": show(d.issue_url), "status": d.status, "overdue": overdue(d),
        "created_by": d.created_by.name if d.created_by else None,
        "created_at": d.created_at.isoformat() if d.created_at else None,
        "updated_at": d.updated_at.isoformat() if d.updated_at else None,
        "closed_at": d.closed_at.isoformat() if d.closed_at else None,
    }


def summary(system: System) -> dict:
    open_ = [d for d in system.tech_debts if d.status not in DEBT_CLOSED]
    return {"open": len(open_), "high_open": sum(1 for d in open_ if d.risk == "High"),
            "overdue": sum(1 for d in open_ if overdue(d))}


def _sorted(debts: list[TechDebt]) -> list[TechDebt]:
    # Open first, riskiest first, then the nearest target date.
    return sorted(debts, key=lambda d: (d.status in DEBT_CLOSED, RISK_ORDER.get(d.risk, 9),
                                        d.target_date or date.max, d.id))


def _list(db: Session, system_id: str, person: Person) -> dict:
    system = svc.get_system(db, system_id)
    show = leak_scan.redactor(person, system)
    return {"items": [debt_json(d, show) for d in _sorted(system.tech_debts)],
            "summary": summary(system), "can_edit": svc.can_edit(person, system)}


def _apply(debt: TechDebt, body: TechDebtIn) -> None:
    clean = lambda v: (v or "").strip() or None  # noqa: E731
    debt.title = body.title.strip()
    debt.description, debt.reason = clean(body.description), clean(body.reason)
    debt.impact, debt.fix_plan = clean(body.impact), clean(body.fix_plan)
    debt.risk, debt.effort = body.risk, clean(body.effort)
    debt.target_date, debt.issue_url = body.target_date, body.issue_url
    if body.status in DEBT_CLOSED and debt.status not in DEBT_CLOSED:
        debt.closed_at = utcnow()
    elif body.status not in DEBT_CLOSED:
        debt.closed_at = None
    debt.status = body.status


@router.get("/systems/{system_id}/tech-debt")
def list_debt(system_id: str, db: Session = Depends(get_db), person: Person = Depends(current_person)):
    return _list(db, system_id, person)


@router.post("/systems/{system_id}/tech-debt", status_code=201)
def add_debt(system_id: str, body: TechDebtIn, guard: LeakGuard = Depends(),
             db: Session = Depends(get_db), person: Person = Depends(current_person)):
    system = svc.get_system(db, system_id)
    svc.require_editor(person, system)
    debt = TechDebt(created_by_id=person.id)
    _apply(debt, body)
    system.tech_debts.append(debt)
    guard.check(system)
    db.commit()
    guard.after(system_id)
    return _list(db, system_id, person)


@router.put("/systems/{system_id}/tech-debt/{debt_id}")
def update_debt(system_id: str, debt_id: int, body: TechDebtIn, guard: LeakGuard = Depends(),
                db: Session = Depends(get_db), person: Person = Depends(current_person)):
    system = svc.get_system(db, system_id)
    svc.require_editor(person, system)
    debt = next((d for d in system.tech_debts if d.id == debt_id), None)
    if debt is None:
        raise HTTPException(status_code=404, detail="ไม่พบรายการหนี้ทางเทคนิคนี้")
    _apply(debt, body)
    guard.check(system)
    db.commit()
    guard.after(system_id)
    return _list(db, system_id, person)


@router.delete("/systems/{system_id}/tech-debt/{debt_id}")
def delete_debt(system_id: str, debt_id: int, guard: LeakGuard = Depends(),
                db: Session = Depends(get_db), person: Person = Depends(current_person)):
    system = svc.get_system(db, system_id)
    svc.require_editor(person, system)
    debt = next((d for d in system.tech_debts if d.id == debt_id), None)
    if debt is None:
        raise HTTPException(status_code=404, detail="ไม่พบรายการหนี้ทางเทคนิคนี้")
    system.tech_debts.remove(debt)
    db.commit()
    guard.after(system_id)
    return _list(db, system_id, person)


@router.get("/tech-debt")
def all_debt(db: Session = Depends(get_db), person: Person = Depends(current_person)):
    """Every system's debt in one list, for leaders planning across systems."""
    systems = db.scalars(select(System).options(
        selectinload(System.tech_debts).selectinload(TechDebt.created_by),
        selectinload(System.roles).selectinload(SystemRole.person),
        selectinload(System.secret_alerts), selectinload(System.secrets),
    )).all()
    items = []
    for system in systems:
        if not system.tech_debts:
            continue
        show = leak_scan.redactor(person, system)
        for d in system.tech_debts:
            items.append({**debt_json(d, show), "system": {"id": system.id, "name": system.name,
                                                          "criticality": system.criticality}})
    items.sort(key=lambda i: (i["status"] in DEBT_CLOSED, RISK_ORDER.get(i["risk"], 9),
                              i["target_date"] or "9999", i["system"]["name"]))
    return items
