"""Provider adapters phase A: registry, normalized results, money ledger, data model, routing (offline, 0 cost)."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from film_pipeline.drama.generability import rate_shot
from film_pipeline.production import generate as G
from film_pipeline.production import takes as T
from film_pipeline.production.money import credit_ledger, money_ledger
from film_pipeline.production.package import Budget, load_package
from film_pipeline.production.planning import flow_credits
from film_pipeline.production.sections import shot_seconds
from film_pipeline.providers.capability import get_capability, load_registry
from film_pipeline.providers.http_adapters import AdapterOutcome
from film_pipeline.providers.request import FrameRef, GenerationRequest, ReferenceRef
from film_pipeline.providers.route import RouteSpec, route_issues
from test_production_generate import FakeRunner, backlog, film, still

# a live generate() send leases a Flow account from the isolated machine pool (tests/conftest.py)
pytestmark = pytest.mark.usefixtures("flow_lease_account")

ROOT = Path(__file__).resolve().parents[1]
FILMS = [ROOT / "films" / "film03_front_desk", ROOT / "films" / "film04_last_ticket"]
GO = "OWNER_GO_LIVE: YES"


# ---- registry -------------------------------------------------------------------------------------------------

def test_registry_has_the_routes_of_the_proposal():
    assert set(load_registry()) == {("flow", "omni-1.2-flash"), ("minimax", "h3-lite"), ("minimax", "h3-highspeed"),
                                    ("minimax", "h3"), ("vilao", "h3-480p"), ("vilao", "h3-768p")}


def test_flow_price_is_flow_credits_and_others_use_their_unit():
    flow = get_capability()
    assert all(flow.price_of(s) == flow_credits(s) for s in [0, 1, 2.5, 3, 8, 10, 10.1, 11, 12, 15])
    assert flow.price.unit == "credits" and flow.duration_s == (3, 15)
    lite = get_capability("minimax", "h3-lite")
    assert lite.price.unit == "USD" and lite.price_of(8) == pytest.approx(0.2) and lite.price_of(8, "FINAL") == 0.32
    assert get_capability("vilao", "h3-480p").price_of(8) == 4158 and get_capability("vilao", "h3-768p").price_of(15) == 5198
    assert get_capability("vilao", "h3-480p").price.unit == "VND"


def test_vilao_frame_mapping_is_marked_unverified():
    for model in ("h3-480p", "h3-768p"):
        cap = get_capability("vilao", model)
        assert any(u.startswith("request_fields") for u in cap.unverified) and "native_audio" in cap.unverified


def test_flow_error_map_is_the_legacy_vocabulary():
    flow = get_capability()
    prefixes = flow.error_map.prefix
    assert {k for k, v in prefixes.items() if v == "NOT_SUBMITTED"} == set(G.PRE_SUBMIT_RESULTS)
    assert {k for k, v in prefixes.items() if v == "PROVIDER_FAILED"} == set(G.FLOW_FAILED_RESULTS)
    cases = {"START_NOT_FOUND tok:abc": "NOT_SUBMITTED", "PRE_SUBMIT_ERROR NO_FLOW_TAB": "NOT_SUBMITTED",
             "SEND_FAILED": "NOT_SUBMITTED", "FLOW_FAILED": "PROVIDER_FAILED", "PASSED": "PASSED",
             "AMBIGUOUS": "AMBIGUOUS", "UNBOUND": "AMBIGUOUS", "TIMEOUT": "AMBIGUOUS", "PENDING": "AMBIGUOUS",
             "NO_VIDEO_UNDER_TILE": "AMBIGUOUS", "SENDER_EXIT_1": "AMBIGUOUS", "NO_MANIFEST": "AMBIGUOUS", None: "AMBIGUOUS"}
    assert {k: flow.normalize(k) for k in cases} == cases
    # charged exactly when it is not a pre-submit failure (the ledger rule before the registry)
    for raw, norm in cases.items():
        assert flow.charged(norm) == (not str(raw).startswith(G.PRE_SUBMIT_RESULTS))


# ---- the ledger numbers of the finished films do not move -----------------------------------------------------

def _legacy_credit_ledger(log, sent):
    """The pre-adapter `generate.credit_ledger`, verbatim."""
    registered = {Path(t.output_file).stem for t in log.takes}
    unresolved = {tid: r["expected_credits"] for tid, r in sent.items()
                  if tid not in registered and not str(r.get("result") or "").startswith(G.PRE_SUBMIT_RESULTS)}
    pre_submit = sorted(tid for tid, r in sent.items()
                        if tid not in registered and str(r.get("result") or "").startswith(G.PRE_SUBMIT_RESULTS))
    logged = sum(t.credits for t in log.takes)
    return {"logged": logged, "unresolved": unresolved, "pre_submit": pre_submit, "spent": logged + sum(unresolved.values())}


@pytest.mark.parametrize("root", FILMS, ids=lambda p: p.name)
def test_film03_and_film04_ledgers_are_unchanged(root):
    pkg = load_package(root)
    prices = {g.generation_id: flow_credits(shot_seconds(g, pkg.header)) for g in pkg.typed["shots"].generations}
    sent = G._sent_receipts(root, pkg.header.film_id, prices)
    log = T.load_log(root, pkg.header.film_id)
    assert credit_ledger(log, sent) == _legacy_credit_ledger(log, sent)
    assert money_ledger(log, sent)["credits"]["spent"] == _legacy_credit_ledger(log, sent)["spent"]
    # the new fallback prices are the old ones for a Flow film
    assert {g: G._fallback_price(pkg.header, d)["expected_credits"] for g, d in
            ((d.generation_id, d) for d in pkg.typed["shots"].generations)} == prices


def test_film04_ledger_figure():
    root = FILMS[1]
    pkg = load_package(root)
    sent = G._sent_receipts(root, pkg.header.film_id, {})
    led = credit_ledger(T.load_log(root, pkg.header.film_id), sent)
    assert led["logged"] == 159.0 and led["spent"] == 231.0 and len(led["pre_submit"]) == 9


# ---- money ledger per unit ------------------------------------------------------------------------------------

def test_money_ledger_keeps_units_apart_and_follows_charged_on():
    sent = {
        "A_t1": {"result": "UNBOUND", "expected_credits": 8.0},                                   # Flow, charged
        "A_t2": {"result": "START_NOT_FOUND x", "expected_credits": 8.0},                          # Flow, free
        "B_t1": {"result": "PROVIDER_FAILED", "provider": "minimax", "provider_model": "h3-lite",
                 "cost_unit": "USD", "expected_cost": 0.2},                                       # MiniMax: not charged
        "B_t2": {"result": "AMBIGUOUS", "provider": "minimax", "provider_model": "h3-lite",
                 "cost_unit": "USD", "expected_cost": 0.2},                                       # MiniMax: reserved
        "C_t1": {"result": "PROVIDER_FAILED", "provider": "vilao", "provider_model": "h3-480p",
                 "cost_unit": "VND", "expected_cost": 4158.0, "provider_job_id": "v1"},           # Vilao: assumed charged
        "C_t2": {"result": "PASSED", "provider": "vilao", "provider_model": "h3-480p",
                 "cost_unit": "VND", "expected_cost": 4158.0, "provider_job_id": "v2"},           # became a take
    }
    take = T.TakeEntry(take_id="C_t1", generation_id="C", prompt_sha256="a" * 64, route="api:first_frame",
                       model="Vilao", credits=0.0, output_file="other.mp4", output_sha256="b" * 64,
                       provider="vilao", provider_job_id="v2", cost_unit="VND", cost_amount=4158.0)
    led = money_ledger(SimpleNamespace(takes=[take]), sent)
    assert led["credits"]["spent"] == 8.0 and led["credits"]["not_submitted"] == ["A_t2"]
    assert led["USD"]["spent"] == 0.2 and led["USD"]["not_charged"] == ["B_t1"] and led["USD"]["unresolved"] == {"B_t2": 0.2}
    assert led["VND"]["unresolved"] == {"C_t1": 4158.0} and led["VND"]["spent"] == 8316.0
    assert credit_ledger(SimpleNamespace(takes=[take]), sent)["spent"] == 8.0


def test_budget_cap_is_per_unit():
    b = Budget(credits_estimate=100, caps={"VND": 30000})
    assert b.cap_for("credits") == 150 and b.cap_for("VND") == 30000 and b.cap_for("USD") is None


# ---- data model ------------------------------------------------------------------------------------------------

def test_old_take_json_loads_as_flow():
    old = {"take_id": "X_t1", "generation_id": "X", "prompt_sha256": "a" * 64, "route": "r", "model": "Omni Flash 360p",
           "credits": 12.0, "output_file": "x.mp4", "output_sha256": "b" * 64}
    entry = T.TakeEntry.model_validate(old)
    assert entry.provider == "flow" and entry.provider_job_id == "" and entry.cost == {
        "amount": 12.0, "unit": "credits", "provider": "flow"}
    for root in FILMS:  # every committed take log still validates
        T.load_log(root, root.name)


def test_an_api_take_binds_by_job_id(tmp_path):
    clip = tmp_path / "c.mp4"
    clip.write_bytes(b"clip")
    kw = dict(prompt_text="p", route="api:first_frame", model="m", credits=0.0, provider="vilao",
              provider_job_id="job-1", cost_unit="VND", cost_amount=4158.0)
    entry, created = T.register_take(tmp_path, "f", "SC01_g1", clip, **kw)
    again, created2 = T.register_take(tmp_path, "f", "SC01_g1", clip, **kw)
    assert created and not created2 and again.take_id == entry.take_id
    assert T.bind_by_job_id(T.load_log(tmp_path, "f"), "vilao", "job-1").take_id == entry.take_id
    other = tmp_path / "d.mp4"
    other.write_bytes(b"other bytes")
    with pytest.raises(ValueError, match="already take"):
        T.register_take(tmp_path, "f", "SC01_g1", other, **kw)


# ---- route preflight and generability per model ----------------------------------------------------------------

def _request(tmp_path, **kw):
    base = dict(film_id="f", generation_id="g", take_id="g_t1", prompt="a prompt", prompt_sha256="c" * 64,
                duration_s=8, first_frame=FrameRef(path=str(tmp_path / "s.png")), output=str(tmp_path / "o.mp4"))
    return GenerationRequest(**{**base, **kw})


def _codes(request, provider, model):
    return [(i.code, i.severity) for i in route_issues(request, get_capability(provider, model))]


def test_route_preflight_refuses_what_the_model_cannot_do(tmp_path):
    assert _codes(_request(tmp_path), "flow", "omni-1.2-flash") == []
    assert ("ROUTE_DURATION", "BLOCK") in _codes(_request(tmp_path, duration_s=4), "vilao", "h3-480p")
    assert ("ROUTE_TIER", "BLOCK") in _codes(_request(tmp_path, tier="FINAL"), "vilao", "h3-480p")
    assert ("ROUTE_TIER", "BLOCK") in _codes(_request(tmp_path, tier="FINAL"), "flow", "omni-1.2-flash")
    refs = [ReferenceRef(role="character", path="r.png")]
    assert ("ROUTE_TOO_MANY_REFS", "BLOCK") in _codes(_request(tmp_path, references=refs), "vilao", "h3-480p")
    assert ("ROUTE_FRAMES_AND_REFS", "BLOCK") in _codes(_request(tmp_path, references=refs), "minimax", "h3-lite")
    assert _codes(_request(tmp_path, first_frame=None, references=refs), "minimax", "h3-lite") == []
    assert ("ROUTE_PROMPT_TOO_LONG", "BLOCK") in _codes(_request(tmp_path, prompt="x" * 7001), "minimax", "h3")


def test_dialogue_on_unknown_audio_warns_and_on_silent_blocks(tmp_path):
    talk = _request(tmp_path, audio_mode="NATIVE_DIALOGUE")
    assert _codes(talk, "flow", "omni-1.2-flash") == []
    assert _codes(talk, "minimax", "h3-lite") == [("ROUTE_NATIVE_AUDIO_UNKNOWN", "WARN")]
    silent = get_capability("minimax", "h3-lite").model_copy(update={"native_audio": "false"})
    assert [(i.code, i.severity) for i in route_issues(talk, silent)] == [("ROUTE_NO_NATIVE_AUDIO", "BLOCK")]


def test_generability_is_keyed_by_provider_and_model():
    pkg = load_package(FILMS[1])
    for decl in pkg.typed["shots"].generations:
        assert rate_shot(decl) == rate_shot(decl, "flow", "omni-1.2-flash")
        other = rate_shot(decl, "vilao", "h3-480p")
        assert other.level == "UNKNOWN" and other.drafts == 1 and [f.rule for f in other.findings] == ["MODEL_UNRATED"]


# ---- generate through the routes -------------------------------------------------------------------------------

def _route(pkg, route, caps=None, shot_route=None):
    root = pkg.root
    header = json.loads((root / "film.json").read_text(encoding="utf-8"))
    header["route"] = route
    if caps is not None:
        header["budget"]["caps"] = caps
    (root / "film.json").write_text(json.dumps(header), encoding="utf-8")
    if shot_route is not None:
        shots = json.loads((root / "04_shots.json").read_text(encoding="utf-8"))
        shots["generations"][0]["route"] = shot_route
        (root / "04_shots.json").write_text(json.dumps(shots), encoding="utf-8")
    return load_package(root)


class FakeAdapter:
    def __init__(self, result="PASSED", job="job-1", bytes_=b"api-video"):
        self.result, self.job, self.bytes, self.calls = result, job, bytes_, []

    def health(self):
        from film_pipeline.providers.base import ProviderHealth
        return ProviderHealth(provider_id="vilao", state="READY", diagnostic_code="FAKE")

    def run(self, request, on_submitted=None):
        import hashlib
        self.calls.append(request)
        if on_submitted:
            on_submitted(self.job)
        if self.result != "PASSED":
            return AdapterOutcome(raw_result="status_failed", result=self.result, provider_job_id=self.job)
        request.output_path.parent.mkdir(parents=True, exist_ok=True)
        request.output_path.write_bytes(self.bytes)
        return AdapterOutcome(raw_result="status_completed", result="PASSED", provider_job_id=self.job,
                              output=request.output, sha256=hashlib.sha256(self.bytes).hexdigest())


def test_default_route_payload_is_flow_and_carries_a_neutral_request(tmp_path):
    pkg = film(tmp_path, 100)
    p = G.build_payload(pkg, "SC01_g1", stills_dir=still(tmp_path), start_token="tok:abc")
    assert (p["provider"], p["provider_model"], p["cost_unit"], p["tier"]) == ("flow", "omni-1.2-flash", "credits", "TEST")
    assert p["expected_cost"] == p["expected_credits"] == 8 and p["argv"][-4:] == ["--model", "Omni 1.2 Flash", "--duration", "8"]
    req = GenerationRequest.model_validate(p["request"])
    assert req.audio_mode == "NATIVE_DIALOGUE" and req.first_frame.path == p["start_frame"]["file"] and req.tier == "TEST"
    assert p["warnings"] == []


def test_an_api_route_sends_through_its_adapter_and_binds_the_take_by_job_id(tmp_path):
    pkg = _route(film(tmp_path, 100), {"provider": "vilao", "model": "h3-480p", "tier": "TEST"}, caps={"VND": 9000})
    dry = G.generate(pkg, "SC01_g1", dry_run=True, stills_dir=still(tmp_path), backlog=backlog(tmp_path))["payload"]
    assert dry["argv"] == [] and dry["cost_unit"] == "VND" and dry["expected_cost"] == 4158 and dry["expected_credits"] == 0
    assert [w["code"] for w in dry["warnings"]] == ["ROUTE_NATIVE_AUDIO_UNKNOWN"]   # SC01_g1 has a line
    adapter = FakeAdapter()
    done = G.generate(pkg, "SC01_g1", dry_run=False, stills_dir=still(tmp_path), backlog=backlog(tmp_path, GO),
                      adapter=adapter)
    assert done["sent"] and done["manifest_result"] == "PASSED" and len(adapter.calls) == 1
    take = done["take"]
    assert (take["provider"], take["provider_job_id"], take["cost_unit"], take["cost_amount"], take["credits"]) == (
        "vilao", "job-1", "VND", 4158.0, 0.0)
    receipt = json.loads(Path(done["receipt"]).read_text(encoding="utf-8"))
    assert receipt["provider_job_id"] == "job-1" and receipt["result"] == "PASSED" and receipt["cost_unit"] == "VND"
    # second send fits (8316 <= 9000), third does not: the VND cap, not the credit cap, rules this route
    G.generate(pkg, "SC01_g1", dry_run=False, stills_dir=still(tmp_path), backlog=backlog(tmp_path, GO),
               adapter=FakeAdapter("PROVIDER_FAILED", job="job-2"))
    third = G.generate(pkg, "SC01_g1", dry_run=False, stills_dir=still(tmp_path), backlog=backlog(tmp_path, GO),
                       adapter=FakeAdapter(job="job-3"))
    assert not third["sent"] and [r["code"] for r in third["refused"]] == ["BUDGET_EXCEEDED"]
    assert third["payload"]["spent_in_unit"] == 8316.0 and third["payload"]["credits_spent"] == 0


def test_an_api_route_without_a_cap_or_key_is_refused(tmp_path, monkeypatch):
    monkeypatch.delenv("VILAO_API_KEY", raising=False)
    monkeypatch.delenv("VILAO_API_KEY_FILE", raising=False)
    pkg = _route(film(tmp_path, 100), {"provider": "vilao", "model": "h3-480p"})
    done = G.generate(pkg, "SC01_g1", dry_run=False, stills_dir=still(tmp_path), backlog=backlog(tmp_path, GO))
    assert not done["sent"] and {r["code"] for r in done["refused"]} == {"BUDGET_NOT_SET", "PROVIDER_NOT_READY"}


def test_a_shot_route_overrides_the_film_route(tmp_path):
    pkg = _route(film(tmp_path, 100), {"provider": "flow", "model": "omni-1.2-flash"},
                 shot_route={"provider": "minimax", "model": "h3-lite", "tier": "TEST"})
    p = G.build_payload(pkg, "SC01_g1", stills_dir=still(tmp_path))
    assert (p["provider"], p["cost_unit"], p["expected_cost"]) == ("minimax", "USD", pytest.approx(0.2))
    assert G.build_payload(pkg, "SC01_g2", stills_dir=still(tmp_path, "SC01_g2"))["provider"] == "flow"


def test_a_route_that_cannot_do_the_shot_blocks_before_any_spend(tmp_path):
    pkg = _route(film(tmp_path, 100), {"provider": "vilao", "model": "h3-480p", "tier": "FINAL"}, caps={"VND": 9000})
    adapter = FakeAdapter()
    done = G.generate(pkg, "SC01_g1", dry_run=False, stills_dir=still(tmp_path), backlog=backlog(tmp_path, GO),
                      adapter=adapter)
    assert not done["sent"] and "ROUTE_TIER" in [r["code"] for r in done["refused"]] and not adapter.calls


def test_unknown_route_is_an_error(tmp_path):
    pkg = _route(film(tmp_path, 100), {"provider": "nobody", "model": "x"})
    with pytest.raises(ValueError, match="capability registry"):
        G.build_payload(pkg, "SC01_g1", stills_dir=still(tmp_path))


def test_flow_route_still_runs_the_flow_runner(tmp_path):
    pkg = film(tmp_path, 100)
    runner = FakeRunner()
    done = G.generate(pkg, "SC01_g1", dry_run=False, stills_dir=still(tmp_path), start_token="tok:abc",
                      backlog=backlog(tmp_path, GO), runner=runner, adapter=FakeAdapter())
    assert done["sent"] and len(runner.calls) == 1 and done["take"]["provider"] == "flow"
    assert done["take"]["credits"] == 8.0 and done["take"]["provider_job_id"] == ""


# ---- Owner 2026-11-09: experiments default to Vilao omh3 h3-480p, 50,000 VND per day -------------------------

def test_existing_films_resolve_to_flow_and_experiments_to_vilao_h3_480p():
    from film_pipeline.providers.route import resolve_route, route_defaults
    for root in FILMS:
        pkg = load_package(root)
        assert resolve_route(pkg.header) == RouteSpec(provider="flow", model="omni-1.2-flash", tier="TEST")
        assert all(resolve_route(pkg.header, d).provider == "flow" for d in pkg.typed["shots"].generations)
    exp = route_defaults().experiment
    cap = exp.capability()
    assert (cap.provider, cap.model, cap.base_url, cap.price_of(8)) == ("vilao", "h3-480p", "https://api.vilao.ai/p/omh3", 4158)
    assert get_capability("vilao", "omh3/h3-480p") is cap and route_defaults().daily_caps == {"VND": 50000}


def _experiment(pkg):
    header = json.loads((pkg.root / "film.json").read_text(encoding="utf-8"))
    header["experiment"] = True
    (pkg.root / "film.json").write_text(json.dumps(header), encoding="utf-8")
    return load_package(pkg.root)


def test_an_experiment_film_routes_to_vilao_and_the_day_cap_holds(tmp_path):
    from datetime import date
    pkg = _experiment(film(tmp_path, 100))
    p = G.build_payload(pkg, "SC01_g1", stills_dir=still(tmp_path))
    assert (p["provider"], p["provider_model"], p["expected_cost"], p["cost_unit"]) == ("vilao", "h3-480p", 4158, "VND")
    assert "BUDGET_NOT_SET" not in [b["code"] for b in p["blockers"]]  # the daily cap governs an experiment film
    for n in range(12):  # 12 x 4158 = 49,896 <= 50,000: all fit
        done = G.generate(pkg, "SC01_g1", dry_run=False, stills_dir=still(tmp_path), backlog=backlog(tmp_path, GO),
                          adapter=FakeAdapter("PROVIDER_FAILED", job=f"j{n}"))
        assert done["sent"], done.get("refused")
    receipt = json.loads(Path(done["receipt"]).read_text(encoding="utf-8"))
    assert receipt["sent_on"] == date.today().isoformat()
    over = G.generate(pkg, "SC01_g1", dry_run=False, stills_dir=still(tmp_path), backlog=backlog(tmp_path, GO),
                      adapter=FakeAdapter(job="j13"))
    assert not over["sent"] and [r["code"] for r in over["refused"]] == ["BUDGET_DAILY_EXCEEDED"]


def test_the_key_comes_from_env_then_from_the_key_file(tmp_path):
    from film_pipeline.providers.http_adapters import OpenAIVideosAdapter, ProviderNotReady
    cap = get_capability("vilao", "h3-480p")
    keyfile = tmp_path / "vilao.txt"
    keyfile.write_text("\ufeff\n  file-key-123  \n", encoding="utf-8")
    assert OpenAIVideosAdapter(cap, env={"VILAO_API_KEY": "env-key"})._key() == "env-key"
    adapter = OpenAIVideosAdapter(cap, env={"VILAO_API_KEY_FILE": str(keyfile)})
    assert adapter._key() == "file-key-123" and adapter.health().state == "READY"
    assert adapter._scrub("boom file-key-123 boom") == "boom *** boom"
    with pytest.raises(ProviderNotReady) as err:
        OpenAIVideosAdapter(cap, env={"VILAO_API_KEY_FILE": str(tmp_path / "missing.txt")})._key()
    assert "missing" not in str(err.value)


# ---- Codex review 2026-11-09 -----------------------------------------------------------------------------------

def test_an_alias_route_counts_the_same_sends(tmp_path):
    canonical = G.build_payload(_route(film(tmp_path / "a", 100), {"provider": "flow", "model": "omni-1.2-flash"}),
                                "SC01_g1", stills_dir=still(tmp_path / "a"))
    alias = G.build_payload(_route(film(tmp_path / "b", 100), {"provider": "flow", "model": "Omni 1.2 Flash"}),
                            "SC01_g1", stills_dir=still(tmp_path / "b"))
    assert canonical["provider_model"] == alias["provider_model"] == "omni-1.2-flash"
    assert canonical["argv"][2:] == [a.replace(str(tmp_path / "b"), str(tmp_path / "a")) for a in alias["argv"][2:]]


def test_the_daily_cap_counts_other_films(tmp_path):
    # S1 (Codex finding 1): spend another film made before S1 (a receipt without ``broker``) still counts against the
    # machine daily cap: it is imported into the broker once, before any admission, and never twice
    from datetime import date
    from film_pipeline.production import leases as L
    other = tmp_path / "films" / "other" / "takes" / "intents"
    other.mkdir(parents=True)
    (other / "X_t1.intent.json").write_text(json.dumps({
        "sent": True, "result": "PASSED", "provider": "vilao", "provider_model": "h3-480p", "cost_unit": "VND",
        "expected_cost": 48000, "sent_on": date.today().isoformat(), "film_id": "other"}), encoding="utf-8")
    root = tmp_path / "films" / "film"
    pkg = _experiment(film(tmp_path / "films" / "x", 100))  # film() makes <arg>/film
    import shutil
    shutil.move(str(pkg.root), str(root))
    pkg = load_package(root)
    # 48,000 elsewhere + 4,158 here > 50,000: the dry run reports it ...
    dry = G.generate(pkg, "SC01_g1", dry_run=True, stills_dir=still(tmp_path))
    assert "BUDGET_DAILY_EXCEEDED" in [b["code"] for b in dry["payload"]["blockers"]]
    # ... and the broker refuses the live admission; the adapter is never called
    adapter = FakeAdapter(job="j1")
    live = G.generate(pkg, "SC01_g1", dry_run=False, stills_dir=still(tmp_path), backlog=backlog(tmp_path, GO),
                      adapter=adapter)
    assert not live["sent"] and [r["code"] for r in live["refused"]] == ["BUDGET_DAILY_EXCEEDED"]
    assert not adapter.calls
    # the import is durable and deduplicated: importing again never counts the receipt twice
    pool = L.machine_pool()
    L.import_legacy_spend(pool, root)
    L.import_legacy_spend(pool, root)
    assert pool.daily_usage("VND", date.today().isoformat()) == 48000.0


def test_an_unreadable_receipt_keeps_its_flow_credits_after_a_reroute(tmp_path):
    pkg = film(tmp_path, 100)
    folder = T.takes_dir(pkg.root) / "intents"
    folder.mkdir(parents=True)
    (folder / "SC01_g1_t1.intent.json").write_text("{not json", encoding="utf-8")
    pkg = _route(pkg, {"provider": "vilao", "model": "h3-480p"}, caps={"VND": 90000})
    prices = {g.generation_id: G._fallback_price(pkg.header, g) for g in pkg.typed["shots"].generations}
    sent = G._sent_receipts(pkg.root, pkg.header.film_id, prices)
    led = money_ledger(T.load_log(pkg.root, pkg.header.film_id), sent)
    assert led["credits"]["unresolved"] == {"SC01_g1_t1": 8.0} and led["VND"]["unresolved"] == {"SC01_g1_t1~VND": 4158.0}


def test_an_experiment_header_keeps_its_route_through_a_save(tmp_path):
    from film_pipeline.production.package import FilmHeader
    from film_pipeline.providers.route import resolve_route
    header = FilmHeader.model_validate({"film_id": "x", "title": "x", "profile": "drama", "experiment": True})
    again = FilmHeader.model_validate_json(header.model_dump_json())
    assert resolve_route(header).provider == resolve_route(again).provider == "vilao"
