"""Founder test-script progress endpoints.

TEMPORARY (Simon, 05/09/2026): the pre-launch walkthrough lives as a
Test script tab in the app so every tester's ticks and problem notes
record centrally under their signed-in name — the standalone checklist
page couldn't send results anywhere. Delete this file, the frontend
TestScript screen + items, the nav entry, and the `test_check_marks`
table (migration 0022 downgrade) together once testing wraps.

The checklist ITEMS live in the frontend (`testScriptItems.ts`) — the
server only stores marks keyed by item id, so wording edits never need
a deploy of anything but the SPA.
"""
from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from l360.db import get_session
from l360.deps import require_user
from l360.models import TestCheckMark, User

router = APIRouter()


class TestMarkIn(BaseModel):
    # None clears the mark (un-tick).
    state: str | None = Field(default=None, pattern="^(pass|flag)$")
    note: str | None = Field(default=None, max_length=4000)


class TestMarkOut(BaseModel):
    item_id: str
    state: str
    note: str | None


class TesterOut(BaseModel):
    user_id: int
    name: str
    marks: list[TestMarkOut]


class TestScriptOut(BaseModel):
    my_user_id: int
    testers: list[TesterOut]


@router.get("/api/test-script", response_model=TestScriptOut)
def get_test_script(db: Session = Depends(get_session), user: User = Depends(require_user)):
    """Everyone signed in sees everyone's progress — the whole point is
    that the founders (and Simon) watch the walkthrough fill in live."""
    rows = db.scalars(select(TestCheckMark)).all()
    users = {u.id: u for u in db.scalars(select(User).where(User.id.in_({r.user_id for r in rows})))}
    by_user: dict[int, list[TestCheckMark]] = {}
    for r in rows:
        by_user.setdefault(r.user_id, []).append(r)
    testers = [
        TesterOut(
            user_id=uid,
            name=users[uid].full_name if uid in users else f"#{uid}",
            marks=[TestMarkOut(item_id=m.item_id, state=m.state, note=m.note) for m in marks],
        )
        for uid, marks in sorted(by_user.items())
    ]
    return TestScriptOut(my_user_id=user.id, testers=testers)


@router.put("/api/test-script/{item_id}")
def set_test_mark(
    item_id: str,
    body: TestMarkIn,
    db: Session = Depends(get_session),
    user: User = Depends(require_user),
):
    if len(item_id) > 20:
        raise HTTPException(status_code=422, detail="Unknown checklist item.")
    row = db.scalar(
        select(TestCheckMark).where(TestCheckMark.user_id == user.id, TestCheckMark.item_id == item_id)
    )
    if body.state is None:
        if row is not None:
            db.delete(row)
            db.commit()
        return {"ok": True}
    if row is None:
        row = TestCheckMark(user_id=user.id, item_id=item_id, state=body.state)
        db.add(row)
    row.state = body.state
    row.note = (body.note or "").strip() or None
    row.updated_at = datetime.now(UTC)
    db.commit()
    return {"ok": True}
