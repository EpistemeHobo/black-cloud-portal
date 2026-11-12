from datetime import datetime, timezone

from fastapi import APIRouter, Body, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app import doc_store, leak_scan, vault
from app import systems_service as svc
from app import transfer
from app.auth import current_person
from app.checklist import evaluate
from app.db import get_db
from app.leak_guard import LeakGuard
from app.models import (
    ChangeLog, ChecklistAnswer, Dependency, GuideDoc, Link, OpenItem, Person, ReviewNote, System, SystemRole,
    Unit, WatchOut,
)
from app.schemas import (
    AnswerIn, DependencyIn, DocIn, LinkIn, OpenItemIn, ReviewIn, RoleIn, StepIn, SystemCreate, WatchOutIn,
)

router = APIRouter(prefix="/api/systems", tags=["systems"])


@router.get("")
def list_systems(db: Session = Depends(get_db), person: Person = Depends(current_person)):
    systems = svc.all_systems(db)
    items_cache: dict = {}
    result = []
    for system in systems:
        key = system.standards_version_id
        if key not in items_cache:
            items_cache[key] = svc.items_for(db, system)
        row = svc.summary(db, system, items_cache[key])
        row["description"] = leak_scan.redactor(person, system)(row["description"])
        result.append(row)
    return result


@router.post("", status_code=201)
def create_system(body: SystemCreate, guard: LeakGuard = Depends(), db: Session = Depends(get_db),
                  person: Person = Depends(current_person)):
    if body.owning_unit_id is not None and db.get(Unit, body.owning_unit_id) is None:
        raise HTTPException(status_code=422, detail="ไม่พบหน่วยงานนี้")
    standards = svc.current_standards(db)
    system = System(
        id=svc.next_system_id(db), name=body.name.strip(), type=body.type, step=body.step,
        description=(body.description or "").strip() or None,
        if_down=(body.if_down or "").strip() or None,
        owning_unit_id=body.owning_unit_id,
        standards_version_id=standards.id if standards else None,
    )
    system.roles.append(SystemRole(person_id=person.id, role="technical_owner"))
    guard.check(system)
    db.add(system)
    db.commit()
    guard.after(system.id)
    return svc.detail(db, svc.get_system(db, system.id), person)


@router.post("/import", status_code=201)
def import_system(body: transfer.ImportIn, guard: LeakGuard = Depends(), db: Session = Depends(get_db),
                  person: Person = Depends(current_person)):
    """Register a new system from an exported folder (system.json plus its .md files).

    Not refused for secrets (the folder came from another portal as it is), but
    scanned in full, so its owners get the alerts at once.
    """
    system = transfer.import_system(db, body, person)
    guard.after(system.id, docs=True)
    return svc.detail(db, svc.get_system(db, system.id), person)


@router.get("/{system_id}/export")
def export_system(system_id: str, db: Session = Depends(get_db), person: Person = Depends(current_person)):
    """The system as a zipped folder. Editors only: it includes the confidential fields."""
    system = svc.get_system(db, system_id)
    svc.require_editor(person, system)
    filename, content = transfer.export_zip(system)
    return Response(content, media_type="application/zip",
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@router.get("/{system_id}")
def get_system(system_id: str, db: Session = Depends(get_db), person: Person = Depends(current_person)):
    return svc.detail(db, svc.get_system(db, system_id), person)


@router.patch("/{system_id}")
def update_system(system_id: str, data: dict = Body(...), guard: LeakGuard = Depends(),
                  db: Session = Depends(get_db), person: Person = Depends(current_person)):
    system = svc.get_system(db, system_id)
    svc.require_patch_rights(person, system, set(data))
    svc.apply_patch(db, system, data)
    guard.check(system)
    db.commit()
    guard.after(system_id)
    return svc.detail(db, svc.get_system(db, system_id), person)


@router.delete("/{system_id}", status_code=204)
def delete_system(system_id: str, db: Session = Depends(get_db), person: Person = Depends(current_person)):
    """Delete a system and everything recorded on it. Its change history is kept."""
    system = svc.get_system(db, system_id)
    if not svc.can_delete(person, system):
        raise HTTPException(status_code=403, detail="เฉพาะเจ้าของฝั่งเทคนิคและผู้ดูแลระบบเท่านั้นที่ลบระบบได้")
    # Other systems that depend on this one lose that line; deleting through the
    # session records it in their history.
    for dep in db.scalars(select(Dependency).where(Dependency.to_system_id == system_id)):
        db.delete(dep)
    db.delete(system)
    db.commit()


@router.put("/{system_id}/step")
def set_step(system_id: str, body: StepIn, db: Session = Depends(get_db),
             person: Person = Depends(current_person)):
    # Guide, don't block: any step is allowed. Missing items stay visible.
    system = svc.get_system(db, system_id)
    svc.require_editor(person, system)
    system.step = body.step
    db.commit()
    return svc.detail(db, svc.get_system(db, system_id), person)


@router.post("/{system_id}/verify")
def verify(system_id: str, db: Session = Depends(get_db), person: Person = Depends(current_person)):
    system = svc.get_system(db, system_id)
    svc.require_editor(person, system)
    system.verified_at = datetime.now(timezone.utc)
    system.verified_by_id = person.id
    db.commit()
    return svc.detail(db, svc.get_system(db, system_id), person)


@router.put("/{system_id}/roles")
def set_roles(system_id: str, body: list[RoleIn], guard: LeakGuard = Depends(),
        db: Session = Depends(get_db),
              person: Person = Depends(current_person)):
    system = svc.get_system(db, system_id)
    svc.require_editor(person, system)
    if not any(r.role == "technical_owner" for r in body):
        raise HTTPException(status_code=422, detail="ระบบต้องมีเจ้าของฝั่งเทคนิคอย่างน้อยหนึ่งคน")
    wanted = {(r.person_id, r.role): r for r in body}
    for person_id, _ in wanted:
        if db.get(Person, person_id) is None:
            raise HTTPException(status_code=422, detail="ไม่พบบุคคลนี้")
    current = {(r.person_id, r.role): r for r in system.roles}
    for key, role in current.items():
        if key not in wanted:
            system.roles.remove(role)
    for key, r in wanted.items():
        note = (r.note or "").strip() or None
        role = current.get(key)
        if role is None:
            system.roles.append(SystemRole(person_id=r.person_id, role=r.role,
                                           reachable_until=r.reachable_until, note=note))
        else:
            role.reachable_until = r.reachable_until
            role.note = note
    guard.check(system)
    db.commit()
    guard.after(system_id)
    return svc.detail(db, svc.get_system(db, system_id), person)


@router.put("/{system_id}/links")
def set_links(system_id: str, body: list[LinkIn], guard: LeakGuard = Depends(),
        db: Session = Depends(get_db),
              person: Person = Depends(current_person)):
    system = svc.get_system(db, system_id)
    svc.require_editor(person, system)
    wanted = [(l.kind, l.url, (l.label or "").strip() or None) for l in body]
    current = {(l.kind, l.url, l.label): l for l in system.links}
    for key, link in current.items():
        if key not in wanted:
            system.links.remove(link)
    for kind, url, label in wanted:
        if (kind, url, label) not in current:
            system.links.append(Link(kind=kind, url=url, label=label))
    guard.check(system)
    db.commit()
    guard.after(system_id)
    return svc.detail(db, svc.get_system(db, system_id), person)


@router.put("/{system_id}/dependencies")
def set_dependencies(system_id: str, body: list[DependencyIn], guard: LeakGuard = Depends(),
        db: Session = Depends(get_db),
                     person: Person = Depends(current_person)):
    system = svc.get_system(db, system_id)
    svc.require_editor(person, system)
    wanted = []
    for d in body:
        external = (d.external_name or "").strip() or None
        if bool(d.to_system_id) == bool(external):
            raise HTTPException(status_code=422, detail="แต่ละรายการที่พึ่งพาต้องระบุระบบในพอร์ทัล หรือชื่อระบบภายนอก อย่างใดอย่างหนึ่ง")
        if d.to_system_id == system_id:
            raise HTTPException(status_code=422, detail="ระบบไม่สามารถพึ่งพาตัวเองได้")
        if d.to_system_id and db.get(System, d.to_system_id) is None:
            raise HTTPException(status_code=422, detail=f"ไม่พบระบบ {d.to_system_id}")
        wanted.append((d.to_system_id or None, external, (d.note or "").strip() or None))
    current = {(d.to_system_id, d.external_name, d.note): d for d in system.dependencies}
    for key, dep in current.items():
        if key not in wanted:
            system.dependencies.remove(dep)
    for to_id, external, note in dict.fromkeys(wanted):
        if (to_id, external, note) not in current:
            system.dependencies.append(Dependency(to_system_id=to_id, external_name=external, note=note))
    if wanted:
        svc.clear_nothing(system, "deps")
    guard.check(system)
    db.commit()
    guard.after(system_id)
    return svc.detail(db, svc.get_system(db, system_id), person)


@router.put("/{system_id}/watch-outs")
def set_watch_outs(system_id: str, body: list[WatchOutIn], guard: LeakGuard = Depends(),
        db: Session = Depends(get_db),
                   person: Person = Depends(current_person)):
    system = svc.get_system(db, system_id)
    svc.require_editor(person, system)
    existing = {w.id: w for w in system.watch_outs}
    keep = set()
    for order, w in enumerate(body):
        item = existing.get(w.id) if w.id else None
        if item is None:
            item = WatchOut()
            system.watch_outs.append(item)
        else:
            keep.add(item.id)
        item.kind = w.kind
        item.text = w.text.strip()
        item.how_often = w.how_often if w.kind == "chore" else None
        item.next_due = w.next_due if w.kind == "chore" else None
        item.sort_order = order
    for item_id, item in existing.items():
        if item_id not in keep:
            system.watch_outs.remove(item)
    if body:
        svc.clear_nothing(system, "watch")
    guard.check(system)
    db.commit()
    guard.after(system_id)
    return svc.detail(db, svc.get_system(db, system_id), person)


@router.put("/{system_id}/open-items")
def set_open_items(system_id: str, body: list[OpenItemIn], guard: LeakGuard = Depends(),
        db: Session = Depends(get_db),
                   person: Person = Depends(current_person)):
    system = svc.get_system(db, system_id)
    svc.require_editor(person, system)
    existing = {o.id: o for o in system.open_items}
    keep = set()
    for order, o in enumerate(body):
        item = existing.get(o.id) if o.id else None
        if item is None:
            item = OpenItem()
            system.open_items.append(item)
        else:
            keep.add(item.id)
        item.kind = o.kind
        item.text = o.text.strip()
        item.promised_to = ((o.promised_to or "").strip() or None) if o.kind == "promise" else None
        item.due_date = o.due_date
        if o.done and item.done_at is None:
            item.done_at = datetime.now(timezone.utc)
            item.done_by = person
        elif not o.done:
            item.done_at = None
            item.done_by = None
        item.sort_order = order
    for item_id, item in existing.items():
        if item_id not in keep:
            system.open_items.remove(item)
    if body:
        svc.clear_nothing(system, "progress")
    guard.check(system)
    db.commit()
    guard.after(system_id)
    return svc.detail(db, svc.get_system(db, system_id), person)


@router.post("/{system_id}/docs")
def upload_doc(system_id: str, body: DocIn, guard: LeakGuard = Depends(), db: Session = Depends(get_db),
               person: Person = Depends(current_person)):
    """Attach a markdown file to a guide question. The same file name replaces the old copy."""
    system = svc.get_system(db, system_id)
    svc.require_editor(person, system)
    # Checked before anything is uploaded: a refused file must not reach S3.
    guard.check(system, [leak_scan.Place("doc", "new", f"ไฟล์แนบ {body.filename}", body.content)])
    doc = next((d for d in system.docs if d.question == body.question and d.filename == body.filename), None)
    if doc is None:
        doc = GuideDoc(question=body.question, filename=body.filename)
        system.docs.append(doc)
    doc_store.save(system, doc, body.content)
    doc.updated_by = person
    svc.clear_nothing(system, body.question)
    db.commit()
    guard.after(system_id, docs=[doc])
    return svc.detail(db, svc.get_system(db, system_id), person)


@router.delete("/{system_id}/docs/{doc_id}")
def delete_doc(system_id: str, doc_id: int, guard: LeakGuard = Depends(), db: Session = Depends(get_db),
               person: Person = Depends(current_person)):
    system = svc.get_system(db, system_id)
    svc.require_editor(person, system)
    doc = next((d for d in system.docs if d.id == doc_id), None)
    if doc is None:
        raise HTTPException(status_code=404, detail="ไม่พบไฟล์นี้")
    system.docs.remove(doc)
    db.commit()
    guard.after(system_id)
    return svc.detail(db, svc.get_system(db, system_id), person)


@router.get("/{system_id}/checklist")
def get_checklist(system_id: str, db: Session = Depends(get_db), person: Person = Depends(current_person)):
    system = svc.get_system(db, system_id)
    show = leak_scan.redactor(person, system)
    result = evaluate(system, svc.items_for(db, system))
    for row in result["items"]:
        row["evidence"] = show(row["evidence"])
    return result


@router.put("/{system_id}/checklist/{code}")
def answer_item(system_id: str, code: str, body: AnswerIn, guard: LeakGuard = Depends(),
                db: Session = Depends(get_db), person: Person = Depends(current_person)):
    system = svc.get_system(db, system_id)
    svc.require_editor(person, system)
    item = next((i for i in svc.items_for(db, system) if i.code == code), None)
    if item is None:
        raise HTTPException(status_code=404, detail="ไม่พบรายการตรวจสอบนี้")
    if item.auto_rule:
        raise HTTPException(status_code=422, detail="พอร์ทัลประเมินรายการนี้ให้โดยอัตโนมัติ")
    answer = next((a for a in system.answers if a.item_id == item.id), None)
    evidence = (body.evidence or "").strip() or None
    if answer is None:
        system.answers.append(ChecklistAnswer(
            item_id=item.id, status=body.status, evidence=evidence, updated_by_id=person.id,
        ))
    else:
        answer.status = body.status
        answer.evidence = evidence
        answer.updated_by_id = person.id
    guard.check(system)
    db.commit()
    guard.after(system_id)
    return evaluate(svc.get_system(db, system_id), svc.items_for(db, system))


@router.get("/{system_id}/reviews")
def list_reviews(system_id: str, db: Session = Depends(get_db), person: Person = Depends(current_person)):
    show = leak_scan.redactor(person, svc.get_system(db, system_id))
    notes = db.scalars(
        select(ReviewNote).where(ReviewNote.system_id == system_id)
        .options(selectinload(ReviewNote.reviewer))
        .order_by(ReviewNote.review_date.desc(), ReviewNote.id.desc())
    ).all()
    return [
        {"id": n.id, "review_date": n.review_date.isoformat(), "place": n.place, "step": n.step,
         "note": show(n.note), "reviewer": {"id": n.reviewer.id, "name": n.reviewer.name},
         "can_delete": person.is_admin or n.reviewer_id == person.id}
        for n in notes
    ]


@router.post("/{system_id}/reviews", status_code=201)
def add_review(system_id: str, body: ReviewIn, guard: LeakGuard = Depends(), db: Session = Depends(get_db),
               person: Person = Depends(current_person)):
    # Any signed-in person can review: leaders and peers alike.
    system = svc.get_system(db, system_id)
    system.reviews.append(ReviewNote(
        reviewer_id=person.id, review_date=body.review_date, place=body.place,
        step=system.step, note=body.note.strip(),
    ))
    guard.check(system)
    db.commit()
    guard.after(system_id)
    return list_reviews(system_id, db, person)


@router.delete("/{system_id}/reviews/{review_id}")
def delete_review(system_id: str, review_id: int, guard: LeakGuard = Depends(), db: Session = Depends(get_db),
                  person: Person = Depends(current_person)):
    note = db.get(ReviewNote, review_id)
    if note is None or note.system_id != system_id:
        raise HTTPException(status_code=404, detail="ไม่พบบันทึกการทบทวนนี้")
    if not (person.is_admin or note.reviewer_id == person.id):
        raise HTTPException(status_code=403, detail="เฉพาะผู้ทบทวนหรือผู้ดูแลระบบเท่านั้นที่ลบบันทึกการทบทวนได้")
    db.delete(note)
    db.commit()
    guard.after(system_id)
    return list_reviews(system_id, db, person)


@router.get("/{system_id}/history")
def history(system_id: str, db: Session = Depends(get_db), person: Person = Depends(current_person)):
    system = svc.get_system(db, system_id)
    hidden = set() if svc.can_edit(person, system) or person.is_auditor else svc.RESTRICTED_FIELDS
    # Vault and alert events: their names are for the people who may see the vault.
    hide_secret_events = not vault.can_list(person, system)
    show = leak_scan.redactor(person, system)
    rows = db.scalars(
        select(ChangeLog).where(ChangeLog.system_id == system_id)
        .options(selectinload(ChangeLog.changed_by))
        .order_by(ChangeLog.changed_at.desc(), ChangeLog.id.desc()).limit(300)
    ).all()
    result = []
    for r in rows:
        is_hidden = r.field in hidden or (r.entity == "secret" and hide_secret_events)
        result.append({
            "changed_at": r.changed_at.isoformat(), "entity": r.entity,
            "entity_id": "" if r.entity == "secret" and hide_secret_events else r.entity_id,
            "field": r.field,
            "old_value": None if is_hidden else show(r.old_value),
            "new_value": None if is_hidden else show(r.new_value),
            "hidden": is_hidden,
            "changed_by": r.changed_by.name if r.changed_by else None,
        })
    return result
