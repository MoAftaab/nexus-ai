from __future__ import annotations

import asyncio

from app.services.event_bus import EventBus


class FakeSocket:
    def __init__(self):
        self.accepted = False
        self.events = []

    async def accept(self):
        self.accepted = True

    async def send_json(self, event):
        self.events.append(event)


def test_event_bus_broadcasts_after_publish_and_disconnects_stale_clients():
    bus = EventBus("redis://localhost:6399")
    first, second = FakeSocket(), FakeSocket()
    asyncio.run(bus.connect(first))
    asyncio.run(bus.connect(second))
    asyncio.run(bus.publish("approval_decided", {"site_id": "wolfsburg", "request_id": "CR-1"}))
    assert first.events[0]["type"] == "approval_decided"
    assert second.events[0]["request_id"] == "CR-1"


def test_event_bus_site_filter_does_not_leak_scoped_events():
    bus = EventBus("redis://localhost:6399")
    wolfsburg, bratislava = FakeSocket(), FakeSocket()
    asyncio.run(bus.connect(wolfsburg, site_scopes=["wolfsburg"]))
    asyncio.run(bus.connect(bratislava, site_scopes=["bratislava"]))
    asyncio.run(bus.publish("change_applied", {"site_id": "wolfsburg", "request_id": "CR-2"}))
    assert len(wolfsburg.events) == 1
    assert bratislava.events == []


def test_approval_api_publishes_after_state_is_persisted(client, login_as, monkeypatch):
    events = []

    async def capture(event_type, payload):
        events.append((event_type, payload))

    import main
    monkeypatch.setattr(main.event_bus, "publish", capture)
    requester = login_as(client, "operator1@nexusai.demo")
    findings = [item for item in client.get("/api/anomalies").json()["items"] if item["actions"]]
    finding = next((item for item in findings if item["severity"] == "low" and item["impact"] < 25_000), findings[0])
    preview = client.post("/api/changes/preview", headers=requester, json={"anomaly_id": finding["id"], "action_id": finding["actions"][0]["id"]}).json()
    request = client.post("/api/changes", headers=requester, json=preview).json()
    client.post(f"/api/changes/{request['request_id']}/submit", headers=requester)
    role = client.get(f"/api/changes/{request['request_id']}", headers=requester).json()["active_step"]["required_role"]
    response = client.post(f"/api/changes/{request['request_id']}/return", headers=login_as(client, {"lead": "lead1@nexusai.demo", "manager": "manager1@nexusai.demo", "quality_compliance": "quality1@nexusai.demo", "director": "director@nexusai.demo"}[role]), json={"comment": "revise"})
    assert response.status_code == 200
    assert any(event[0] in {"change_returned", "approval_decided"} for event in events)
    assert client.get(f"/api/changes/{request['request_id']}", headers=requester).json()["status"] == "returned"
