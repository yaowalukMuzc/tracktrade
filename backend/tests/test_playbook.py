"""Playbook (F-04 AC1-AC2) + attachments: setups, checklist order, examples, archive vs delete."""

from __future__ import annotations

import struct
import zlib
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import text

from tests.conftest import auth, signup

SETUPS = "/api/v1/setups"
ATTACH = "/api/v1/attachments"

LONDON: dict[str, Any] = {
    "name": "London Breakout",
    "description": "รอ Asia range แล้วเข้าเมื่อ London เบรก high/low พร้อม pullback",
    "timeframes": ["M15", "H1"],
    "sessions": ["london"],
    "default_risk_pct": "1",
    "management_rules": {
        "partial": {"pct": "50", "at_r": "1.5"},
        "break_even": {"at_r": "1"},
        "trailing": {"method": "Swing low M15"},
    },
    "checklist": [
        {"text": "H4 bias ตรงทิศทาง", "is_required": True},
        {"text": "ราคาอยู่ใน demand / supply zone"},
        {"text": "มีแท่ง confirm บน M15", "is_required": True},
    ],
}


def png(width: int = 2, height: int = 2) -> bytes:
    """A tiny valid PNG."""

    def chunk(kind: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
        )

    raw = b"".join(b"\x00" + b"\xff\x00\x00" * width for _ in range(height))
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )


async def _user(app: FastAPI, email: str = "nook@example.com") -> dict[str, str]:
    return auth((await signup(app, email))["access_token"])


async def _setup(client: httpx.AsyncClient, h: dict[str, str], **over: Any) -> dict[str, Any]:
    res = await client.post(SETUPS, headers=h, json={**LONDON, **over})
    assert res.status_code == 201, res.text
    body: dict[str, Any] = res.json()
    return body


async def _upload(client: httpx.AsyncClient, h: dict[str, str], data: bytes | None = None) -> str:
    res = await client.post(
        ATTACH, headers=h, files={"file": ("a.png", data or png(), "image/png")}
    )
    assert res.status_code == 201, res.text
    att_id: str = res.json()["id"]
    return att_id


async def test_create_setup_with_checklist_and_rules(
    client: httpx.AsyncClient, app: FastAPI
) -> None:
    h = await _user(app)
    s = await _setup(client, h)
    assert s["timeframes"] == ["M15", "H1"]
    assert s["default_risk_pct"] == "1.00"
    assert s["management_rules"]["partial"] == {"pct": "50", "at_r": "1.5"}
    assert [(i["text"], i["is_required"]) for i in s["checklist"]] == [
        ("H4 bias ตรงทิศทาง", True),
        ("ราคาอยู่ใน demand / supply zone", False),
        ("มีแท่ง confirm บน M15", True),
    ]
    assert s["checklist_count"] == 3
    assert s["stats"] == {
        "trades": 0,
        "win_rate": None,
        "expectancy_r": None,
        "avg_adherence": None,
        "avg_quality": None,
        "avg_quality_grade": None,
    }


@pytest.mark.parametrize(
    "bad",
    [
        {"name": "  "},
        {"timeframes": ["M2"]},
        {"sessions": ["sydney"]},
        {"default_risk_pct": "0"},
        {"management_rules": {"partial": {"pct": "100", "at_r": "1"}}},
        {"management_rules": {"teleport": {}}},
        {"checklist": [{"text": ""}]},
    ],
)
async def test_setup_validation(
    client: httpx.AsyncClient, app: FastAPI, bad: dict[str, Any]
) -> None:
    h = await _user(app)
    assert (await client.post(SETUPS, headers=h, json={**LONDON, **bad})).status_code == 422


async def test_checklist_reorder_keeps_ids(client: httpx.AsyncClient, app: FastAPI) -> None:
    h = await _user(app)
    s = await _setup(client, h)
    a, b, c = s["checklist"]
    items = [
        {"id": c["id"], "text": c["text"], "is_required": True},
        {"id": a["id"], "text": "H4 bias ตรงทิศทาง (แก้)", "is_required": False},
        {"text": "ไม่มีข่าว high impact ใน 30 นาที", "is_required": True},
    ]
    res = await client.put(f"{SETUPS}/{s['id']}/checklist", headers=h, json=items)
    assert res.status_code == 200, res.text
    out = res.json()["checklist"]
    assert [i["id"] for i in out[:2]] == [c["id"], a["id"]]
    assert out[1]["text"].endswith("(แก้)") and out[1]["is_required"] is False
    assert b["id"] not in {i["id"] for i in out}  # dropped
    # An id from another setup is rejected.
    other = await _setup(client, h, name="NY Reversal")
    foreign = [{"id": other["checklist"][0]["id"], "text": "x"}]
    assert (
        await client.put(f"{SETUPS}/{s['id']}/checklist", headers=h, json=foreign)
    ).status_code == 422


async def test_list_active_archived_counts(client: httpx.AsyncClient, app: FastAPI) -> None:
    h = await _user(app)
    london = await _setup(client, h)
    await _setup(client, h, name="NY Reversal", checklist=[])
    await client.post(f"{SETUPS}/{london['id']}/archive", headers=h)
    active = (await client.get(SETUPS, headers=h)).json()
    assert [s["name"] for s in active["items"]] == ["NY Reversal"]
    assert active["counts"] == {"active": 1, "archived": 1}
    archived = (await client.get(SETUPS, headers=h, params={"archived": True})).json()
    assert [(s["name"], s["checklist_count"]) for s in archived["items"]] == [
        ("London Breakout", 3)
    ]
    back = (await client.post(f"{SETUPS}/{london['id']}/unarchive", headers=h)).json()
    assert back["is_archived"] is False


async def test_update_setup(client: httpx.AsyncClient, app: FastAPI) -> None:
    h = await _user(app)
    s = await _setup(client, h)
    res = await client.patch(
        f"{SETUPS}/{s['id']}",
        headers=h,
        json={"default_risk_pct": "0.75", "management_rules": {"break_even": {"at_r": "1"}}},
    )
    assert res.json()["default_risk_pct"] == "0.75"
    assert res.json()["management_rules"] == {
        "partial": None,
        "break_even": {"at_r": "1"},
        "trailing": None,
    }


async def test_unused_setup_can_be_deleted_with_its_images(
    client: httpx.AsyncClient, app: FastAPI
) -> None:
    h = await _user(app)
    s = await _setup(client, h)
    att = await _upload(client, h)
    await client.post(
        f"{SETUPS}/{s['id']}/examples", headers=h, json={"attachment_id": att, "note": "A+"}
    )
    assert (await client.delete(f"{SETUPS}/{s['id']}", headers=h)).status_code == 204
    assert (await client.get(f"{SETUPS}/{s['id']}", headers=h)).status_code == 404
    assert (await client.get(f"{ATTACH}/{att}/content", headers=h)).status_code == 404


async def test_used_setup_cannot_be_deleted_only_archived(
    client: httpx.AsyncClient, app: FastAPI
) -> None:
    """F-04 AC2. Trade plans (Phase 3) reference setups with ON DELETE RESTRICT; a stand-in
    table with the same constraint proves the delete is refused with 409 and nothing is lost."""
    h = await _user(app)
    s = await _setup(client, h)
    async with app.state.engine.begin() as conn:
        await conn.execute(
            text(
                "CREATE TABLE IF NOT EXISTS test_setup_refs ("
                " setup_id uuid REFERENCES setups(id) ON DELETE RESTRICT)"
            )
        )
        await conn.execute(text("INSERT INTO test_setup_refs VALUES (:id)"), {"id": s["id"]})
    try:
        res = await client.delete(f"{SETUPS}/{s['id']}", headers=h)
        assert res.status_code == 409
        assert res.json()["code"] == "setup_in_use"
        still = await client.get(f"{SETUPS}/{s['id']}", headers=h)
        assert still.status_code == 200 and len(still.json()["checklist"]) == 3
        archived = await client.post(f"{SETUPS}/{s['id']}/archive", headers=h)
        assert archived.json()["is_archived"] is True
    finally:
        async with app.state.engine.begin() as conn:
            await conn.execute(text("DROP TABLE test_setup_refs"))


async def test_examples_upload_view_remove(client: httpx.AsyncClient, app: FastAPI) -> None:
    h = await _user(app)
    s = await _setup(client, h)
    data = png()
    att = await _upload(client, h, data)
    res = await client.post(
        f"{SETUPS}/{s['id']}/examples", headers=h, json={"attachment_id": att, "note": "A+"}
    )
    assert res.status_code == 201, res.text
    example = res.json()["examples"][0]
    assert example["note"] == "A+"
    img = await client.get(example["url"], headers=h)
    assert img.status_code == 200
    assert img.headers["content-type"] == "image/png"
    assert img.content == data
    # The same image cannot be attached twice; an attached image cannot be deleted directly.
    again = await client.post(
        f"{SETUPS}/{s['id']}/examples", headers=h, json={"attachment_id": att}
    )
    assert again.status_code == 409
    assert (await client.delete(f"{ATTACH}/{att}", headers=h)).status_code == 409

    removed = await client.delete(f"{SETUPS}/{s['id']}/examples/{example['id']}", headers=h)
    assert removed.status_code == 200 and removed.json()["examples"] == []
    assert (await client.get(f"{ATTACH}/{att}/content", headers=h)).status_code == 404


@pytest.mark.parametrize(
    ("payload", "status", "code"),
    [
        (b"GIF89a....", 415, "unsupported_file_type"),
        (b"<svg xmlns='http://www.w3.org/2000/svg'/>", 415, "unsupported_file_type"),
        (b"\x89PNG\r\n\x1a\n" + b"0" * (10 * 1024 * 1024), 413, "file_too_large"),
    ],
    ids=["gif", "svg", "over_10mb"],
)
async def test_upload_rejects_bad_files(
    client: httpx.AsyncClient, app: FastAPI, payload: bytes, status: int, code: str
) -> None:
    h = await _user(app)
    # The client's content type is ignored: the bytes decide.
    res = await client.post(ATTACH, headers=h, files={"file": ("x.png", payload, "image/png")})
    assert res.status_code == status
    assert res.json()["code"] == code


async def test_other_users_setups_and_files_are_404(
    client: httpx.AsyncClient, app: FastAPI
) -> None:
    alice = await _user(app, "alice@example.com")
    bob = await _user(app, "bob@example.com")
    s = await _setup(client, alice)
    att = await _upload(client, alice)
    bob_att = await _upload(client, bob)
    base = f"{SETUPS}/{s['id']}"
    calls = [
        ("GET", base, None),
        ("PATCH", base, {"name": "x"}),
        ("DELETE", base, None),
        ("PUT", f"{base}/checklist", []),
        ("POST", f"{base}/archive", None),
        ("GET", f"{base}/stats", None),
        ("POST", f"{base}/examples", {"attachment_id": bob_att}),
        ("GET", f"{ATTACH}/{att}/content", None),
        ("DELETE", f"{ATTACH}/{att}", None),
    ]
    for method, url, body in calls:
        res = await client.request(method, url, headers=bob, json=body)
        assert res.status_code == 404, f"{method} {url} -> {res.status_code}"
    # Bob cannot attach Alice's image to his own setup either.
    mine = await _setup(client, bob, name="Bob setup")
    res = await client.post(
        f"{SETUPS}/{mine['id']}/examples", headers=bob, json={"attachment_id": att}
    )
    assert res.status_code == 404
    assert (await client.get(SETUPS, headers=bob)).json()["counts"] == {"active": 1, "archived": 0}
