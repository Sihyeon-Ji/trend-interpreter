import asyncio

import httpx
import pytest
import pytest_asyncio

from model_gateway.app import Generate, Settings, create_app

TOKEN = "synthetic-test-token-" + "x" * 32
DIGEST = "a" * 64


@pytest_asyncio.fixture
async def runtime(tmp_path):
    state = {"calls": [], "digest": DIGEST, "vram": 1024, "fail": False, "stall": False}

    async def backend(request):
        state["calls"].append(request)
        if state["stall"]:
            await asyncio.sleep(10)
        if state["fail"]:
            return httpx.Response(500, text="private backend error")
        if request.url.path == "/api/ps":
            return httpx.Response(
                200,
                json={
                    "models": [
                        {
                            "name": "audit:approved",
                            "digest": state["digest"],
                            "size_vram": state["vram"],
                        }
                    ]
                },
            )
        return httpx.Response(
            200,
            json={
                "model": "audit:approved",
                "done": True,
                "message": {"content": "synthetic output"},
            },
        )

    config = Settings(
        TOKEN,
        "audit:approved",
        DIGEST,
        deadline=0.2,
        lock_path=str(tmp_path / "owner.lock"),
    )
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(backend), base_url="http://127.0.0.1:11434"
    ) as engine:
        app = create_app(config, engine)
        async with (
            app.router.lifespan_context(app),
            httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://gateway"
            ) as client,
        ):
            yield client, app, state, config


def headers():
    return {"authorization": "Bearer " + TOKEN}


async def warm(client):
    response = await client.get("/ready", headers=headers())
    assert response.status_code == 200


async def test_liveness_is_not_readiness_and_requires_real_probe(runtime):
    client, app, state, _ = runtime
    assert (await client.get("/health")).json() == {"live": True}
    assert not app.state.gateway.ready
    response = await client.post("/v1/generate", json={"prompt": "hello"}, headers=headers())
    assert response.status_code == 503 and not state["calls"]
    await warm(client)
    assert [r.url.path for r in state["calls"]] == ["/api/chat", "/api/ps"]


@pytest.mark.parametrize("path,method", [("/ready", "GET"), ("/v1/generate", "POST")])
async def test_unauthorized_calls_never_reach_engine(runtime, path, method):
    client, _, state, _ = runtime
    response = await client.request(
        method, path, content=b"not json", headers={"authorization": "invalid"}
    )
    assert response.status_code == 401
    assert not state["calls"]


@pytest.mark.parametrize("field,value", [("digest", "b" * 64), ("vram", 0)])
async def test_ready_requires_matching_digest_and_gpu_residency(runtime, field, value):
    client, app, state, _ = runtime
    state[field] = value
    response = await client.get("/ready", headers=headers())
    assert response.status_code == 503 and not app.state.gateway.ready


async def test_fixed_model_and_bounded_options(runtime):
    import json

    client, _, state, _ = runtime
    await warm(client)
    response = await client.post(
        "/v1/generate",
        json={"prompt": "synthetic input", "max_tokens": 16},
        headers=headers(),
    )
    assert response.status_code == 200 and response.json()["model_digest"] == DIGEST
    body = json.loads(state["calls"][-1].content)
    assert body["model"] == "audit:approved" and body["think"] is False
    assert body["stream"] is False and body["options"]["num_predict"] == 16
    assert body["messages"] == [{"role": "user", "content": "synthetic input"}]


@pytest.mark.parametrize(
    "payload",
    [
        {"prompt": "hi", "model": "other"},
        {"prompt": "hi", "max_tokens": 513},
        {"prompt": ""},
    ],
)
async def test_arbitrary_models_and_invalid_inputs_are_rejected(runtime, payload):
    client, _, state, _ = runtime
    response = await client.post("/v1/generate", json=payload, headers=headers())
    assert response.status_code == 422 and not state["calls"]


async def test_chunked_body_limit_is_enforced(runtime):
    client, _, state, _ = runtime

    async def chunks():
        for _ in range(5):
            yield b"x" * 16000

    response = await client.post("/v1/generate", content=chunks(), headers=headers())
    assert response.status_code == 413 and not state["calls"]


async def test_model_management_is_not_exposed(runtime):
    client, _, state, _ = runtime
    for path in ("/api/pull", "/api/delete", "/docs", "/openapi.json"):
        assert (await client.post(path, headers=headers())).status_code == 404
    assert not state["calls"]


async def test_deadline_quarantines_until_a_successful_readiness_probe(runtime):
    client, app, state, _ = runtime
    await warm(client)
    state["stall"] = True
    response = await client.post("/v1/generate", json={"prompt": "hello"}, headers=headers())
    assert (
        response.status_code == 504 and not app.state.gateway.ready and not app.state.gateway.busy
    )
    state["stall"] = False
    count = len(state["calls"])
    assert (
        await client.post("/v1/generate", json={"prompt": "hello"}, headers=headers())
    ).status_code == 503
    assert len(state["calls"]) == count
    await warm(client)


async def test_global_busy_slot_rejects_parallel_requests(runtime):
    client, app, state, _ = runtime
    await warm(client)
    state["stall"] = True
    first = asyncio.create_task(
        client.post("/v1/generate", json={"prompt": "hello"}, headers=headers())
    )
    while not app.state.gateway.busy:
        await asyncio.sleep(0)
    second = await client.get("/ready", headers=headers())
    assert second.status_code == 429
    await first


async def test_only_one_gateway_process_can_own_engine(runtime):
    _, _, _, config = runtime
    other = create_app(config)
    with pytest.raises(BlockingIOError):
        async with other.router.lifespan_context(other):
            pass


async def test_cancel_and_disconnect_quarantine(runtime):
    _, app, state, _ = runtime
    state["stall"] = True
    gateway = app.state.gateway
    gateway.ready = True

    class Request:
        async def receive(self):
            return {"type": "http.disconnect"}

    from fastapi import HTTPException

    with pytest.raises(HTTPException) as error:
        await gateway.execute(Request(), Generate(prompt="hello"))
    assert error.value.status_code == 499 and not gateway.ready and not gateway.busy


async def test_backend_error_does_not_return_private_error_text(runtime):
    client, _, state, _ = runtime
    state["fail"] = True
    response = await client.get("/ready", headers=headers())
    assert response.json() == {"detail": "gpu_unavailable"}


async def test_task_cancellation_releases_slot_and_quarantines(runtime):
    _, app, state, _ = runtime
    state["stall"] = True
    gateway = app.state.gateway
    gateway.ready = True

    class Request:
        async def receive(self):
            await asyncio.Event().wait()

    task = asyncio.create_task(gateway.execute(Request(), Generate(prompt="hello")))
    while not gateway.busy:
        await asyncio.sleep(0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert not gateway.busy and not gateway.ready


async def test_boolean_vram_is_not_gpu_evidence(runtime):
    client, _, state, _ = runtime
    state["vram"] = True
    assert (await client.get("/ready", headers=headers())).status_code == 503
