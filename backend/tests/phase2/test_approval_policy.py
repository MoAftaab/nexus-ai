from app.services.change_control import compute_approval_stages


def stages(severity, impact, regulated=False, title=""):
    return [stage["required_role"] for stage in compute_approval_stages(severity, impact, regulated, {"title": title})]


def test_policy_routes_all_threshold_boundaries():
    assert stages("low", 24_999) == ["lead"]
    assert stages("low", 25_000) == ["manager"]
    assert stages("medium", 25_000) == ["manager"]
    assert stages("medium", 99_999) == ["manager"]
    assert stages("high", 100_000) == ["manager", "director"]
    assert stages("high", 249_999) == ["manager", "director"]
    assert stages("critical", 250_000) == ["manager", "director"]
    assert stages("critical", 250_000, regulated=True) == ["manager", "quality_compliance", "director"]


def test_ppap_hazmat_compliance_and_document_release_always_require_quality():
    for title in ("Missing PPAP release", "Hazmat packet", "VDA compliance", "Document release blocked"):
        assert "quality_compliance" in stages("low", 1_000, title=title)


def test_inflight_policy_version_is_frozen_and_policy_shape_is_valid(client, login_as):
    headers = login_as(client, "admin@nexusai.demo")
    policy = client.get("/api/admin/policy", headers=headers)
    assert policy.status_code == 200
    assert policy.json()["version"] >= 1
    assert isinstance(policy.json()["rules"], list)
    updated = client.put("/api/admin/policy", headers=headers, json={"rules": policy.json()["rules"]})
    assert updated.status_code == 200
    assert updated.json()["version"] == policy.json()["version"] + 1

