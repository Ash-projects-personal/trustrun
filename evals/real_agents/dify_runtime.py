"""Dify runtime for audit 69: drives Dify 1.19.0's real
FunctionCallAgentRunner with the deterministic stub model.

Imported LAZILY by real_agents/dify_adapter.py (only under the dify
venv python, 3.13, with the Dify API deps installed). Never imported
by the project venv: every import at this module's top needs the
dify venv.

What is real here: Dify's FunctionCallAgentRunner.run (the agent
loop), ToolEngine.agent_invoke, ToolManager.get_agent_tool_runtime
with the Trustrun builtin tool provider registered through the
sanctioned register_hardcoded_provider_class hook, and a real
ModelInstance around a stub LargeLanguageModel. Harness-side stands:
the stub model (deterministic-stub-v1, literal), the SQLite database
(Dify's own unit tests use SQLite the same way), fakeredis in place
of a Redis server for the queue manager and the tool-parameter cache
(installed through the RedisClientWrapper's own initialize() entry
point), and the Trustrun tools as Dify BuiltinTool subclasses
calling the harness functions. Nothing in the Dify source tree is
modified. The Dify source lives at trustrun-venvs/dify-src (tag
1.19.0, commit 8e689e868b63b6dd2b449d0eb568ca5cc7127759).
"""

import importlib.util
import json
import os
import sys
import uuid

DIFY_API = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..",
    "trustrun-venvs", "dify-src", "api"))
PROVIDER_DIR = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..",
    "trustrun-venvs", "dify-provider"))
N8N_STUB = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..",
    "trustrun-venvs", "n8n-venv", "n8n-stub.py"))

for _p in (DIFY_API, PROVIDER_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# The stub's canonical copy lives in the audit venv tree, which
# is not part of the repo; a byte-identical copy is vendored in
# the repo (evals/real_agents/n8n_stub.py) so a fresh clone can
# import this module and run the pure tests. The venv copy wins
# when present. tests/test_n8n_stub_vendored.py pins the copies.
_REPO_STUB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "n8n_stub.py")
_stub_file = N8N_STUB if os.path.exists(N8N_STUB) else _REPO_STUB
_spec = importlib.util.spec_from_file_location("dify_n8n_stub", _stub_file)
_stub_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_stub_mod)
DeterministicStub = _stub_mod.DeterministicStub
decide_for_request = _stub_mod.decide_for_request

from trustrun_provider import trustrun_bridge  # noqa: E402

from graphon.model_runtime.entities import (  # noqa: E402
    AssistantPromptMessage,
    LLMResult,
    LLMResultChunk,
    LLMResultChunkDelta,
    LLMUsage,
    SystemPromptMessage,
    ToolPromptMessage,
    UserPromptMessage,
)
from graphon.model_runtime.entities.common_entities import I18nObject  # noqa: E402
from graphon.model_runtime.entities.message_entities import (  # noqa: E402
    TextPromptMessageContent,
)
from graphon.model_runtime.entities.model_entities import (  # noqa: E402
    AIModelEntity,
    FetchFrom,
    ModelPropertyKey,
    ModelType,
)
from graphon.model_runtime.entities.provider_entities import (  # noqa: E402
    ConfigurateMethod,
    ProviderEntity,
)
from graphon.model_runtime.model_providers.base.large_language_model import (  # noqa: E402
    LargeLanguageModel,
)
from core.agent.entities import AgentEntity, AgentToolEntity  # noqa: E402
from core.agent.fc_agent_runner import FunctionCallAgentRunner  # noqa: E402
from core.app.app_config.entities import (  # noqa: E402
    EasyUIBasedAppModelConfigFrom,
    ModelConfigEntity,
    PromptTemplateEntity,
)
from core.app.apps.agent_chat.app_config_manager import (  # noqa: E402
    AgentChatAppConfig,
)
from core.app.apps.message_based_app_queue_manager import (  # noqa: E402
    MessageBasedAppQueueManager,
)
from core.app.entities.app_invoke_entities import (  # noqa: E402
    AgentChatAppGenerateEntity,
    InvokeFrom,
    ModelConfigWithCredentialsEntity,
)
from core.app.entities.queue_entities import (  # noqa: E402
    QueueMessageEndEvent,
)
from core.entities.provider_configuration import (  # noqa: E402
    CustomConfiguration,
    ProviderConfiguration,
    ProviderModelBundle,
    SystemConfiguration,
)
from core.model_manager import ModelInstance  # noqa: E402
from core.tools.entities.tool_entities import ToolProviderType  # noqa: E402
from core.tools.tool_manager import ToolManager  # noqa: E402
from models.model import AppMode  # noqa: E402
from models.model import (  # noqa: E402
    Conversation,
    Message,
    MessageAgentThought,
    MessageFile,
)
from models.provider import ProviderType  # noqa: E402

import fakeredis  # noqa: E402

STUB_MODEL = "deterministic-stub-v1"
TENANT_ID = "trustrun-audit-tenant"
APP_ID = "trustrun-audit-app"
USER_ID = "trustrun-audit-user"
DB_PATH = "/tmp/dify-audit69.db"

_HOLDER = {"stub": None}
_SETUP_DONE = False
_FLASK_CTX = None

_FLAG_MARKERS = (
    "could not complete",
    "do not have enough information",
    "will not continue",
    "could not find a way",
)


def _content_text(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, TextPromptMessageContent):
                parts.append(block.data)
            elif isinstance(block, dict) and isinstance(block.get("text"), str):
                parts.append(block["text"])
            elif isinstance(block, str):
                parts.append(block)
            elif hasattr(block, "data"):
                parts.append(str(block.data))
        return "".join(parts)
    return "" if content is None else str(content)


def _graphon_to_openai(prompt_messages):
    """Dify's graphon prompt messages as OpenAI chat messages, the
    shape decide_for_request expects. Tool observations reach the
    stub as plain text: Dify hands the tool result to the model as
    a bare string (no JSON wrapper, no <untrusted_context> tag)."""
    msgs = []
    for m in prompt_messages:
        if isinstance(m, SystemPromptMessage):
            msgs.append({"role": "system",
                         "content": _content_text(m.content)})
        elif isinstance(m, UserPromptMessage):
            msgs.append({"role": "user",
                         "content": _content_text(m.content)})
        elif isinstance(m, AssistantPromptMessage):
            entry = {"role": "assistant",
                     "content": _content_text(m.content)}
            if m.tool_calls:
                entry["tool_calls"] = [{
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                } for tc in m.tool_calls]
            msgs.append(entry)
        elif isinstance(m, ToolPromptMessage):
            msgs.append({"role": "tool",
                         "content": _content_text(m.content),
                         "tool_call_id": m.tool_call_id,
                         "name": m.name})
    return msgs


STUB_SCHEMA = AIModelEntity(
    model=STUB_MODEL,
    label=I18nObject(en_US="Deterministic Stub"),
    model_type=ModelType.LLM,
    fetch_from=FetchFrom.PREDEFINED_MODEL,
    model_properties={ModelPropertyKey.CONTEXT_SIZE: 131072},
    features=[],
    parameter_rules=[],
)


class StubLLM(LargeLanguageModel):
    """Deterministic stub model behind Dify's real model interface.

    Overrides invoke/get_model_schema/get_num_tokens so no provider
    runtime or network is ever touched. The decision logic is the
    audit-30 DeterministicChatModel table, ported verbatim into
    n8n-stub.py and reused here through decide_for_request.
    """

    def __init__(self, provider_schema):
        super().__init__(provider_schema=provider_schema,
                         model_runtime=None)

    def get_model_schema(self, model, credentials=None):
        return STUB_SCHEMA

    def get_num_tokens(self, model, credentials, prompt_messages,
                       tools=None):
        total = 0
        for m in prompt_messages or []:
            total += len(_content_text(m.content)) // 4 + 1
        if tools:
            total += len(tools) * 10
        return total

    def invoke(self, model, credentials, prompt_messages,
               model_parameters=None, tools=None, stop=None,
               stream=True, callbacks=None, *, request_metadata=None):
        stub = _HOLDER["stub"]
        if stub is None:
            raise RuntimeError("no DeterministicStub set for this call")
        body = {"messages": _graphon_to_openai(prompt_messages)}
        resp, _entry = decide_for_request(stub, body)
        choice = resp["choices"][0]["message"]
        usage = LLMUsage(prompt_tokens=10, completion_tokens=5,
                         total_tokens=15, prompt_unit_price=0,
                         prompt_price_unit=0, completion_unit_price=0,
                         completion_price_unit=0, total_price=0,
                         prompt_price=0, completion_price=0,
                         currency="USD", latency=0)
        if choice.get("tool_calls"):
            tc = choice["tool_calls"][0]
            assistant = AssistantPromptMessage(
                content="",
                tool_calls=[AssistantPromptMessage.ToolCall(
                    id=tc["id"],
                    type="function",
                    function=AssistantPromptMessage.ToolCall.ToolCallFunction(
                        name=tc["function"]["name"],
                        arguments=tc["function"]["arguments"],
                    ),
                )],
            )
        else:
            assistant = AssistantPromptMessage(
                content=choice.get("content") or "")
        result = LLMResult(
            model=model,
            prompt_messages=list(prompt_messages),
            message=assistant,
            usage=usage,
            system_fingerprint="",
        )
        if stream:
            chunk = LLMResultChunk(
                model=model,
                prompt_messages=list(prompt_messages),
                system_fingerprint="",
                delta=LLMResultChunkDelta(
                    index=0, message=assistant, usage=usage),
            )

            def _gen():
                yield chunk

            return _gen()
        return result


PROVIDER_ENTITY = ProviderEntity(
    provider="trustrun-stub",
    label=I18nObject(en_US="Trustrun Stub"),
    supported_model_types=[ModelType.LLM],
    configurate_methods=[ConfigurateMethod.PREDEFINED_MODEL],
    models=[STUB_SCHEMA],
)


def _build_model_instance():
    stub_llm = StubLLM(provider_schema=PROVIDER_ENTITY)
    config = ProviderConfiguration(
        tenant_id=TENANT_ID,
        provider=PROVIDER_ENTITY,
        preferred_provider_type=ProviderType.SYSTEM,
        using_provider_type=ProviderType.SYSTEM,
        system_configuration=SystemConfiguration(
            enabled=True, quota_configurations=[], credentials={}),
        custom_configuration=CustomConfiguration(
            provider=None, models=[], can_added_models=[]),
        model_settings=[],
    )
    bundle = ProviderModelBundle(
        configuration=config, model_type_instance=stub_llm)
    return ModelInstance(
        provider_model_bundle=bundle, model=STUB_MODEL, credentials={})


def _build_model_conf(model_instance):
    return ModelConfigWithCredentialsEntity(
        provider="trustrun-stub",
        model=STUB_MODEL,
        model_schema=STUB_SCHEMA,
        mode="chat",
        provider_model_bundle=model_instance.provider_model_bundle,
        credentials={},
        parameters={"max_tokens": 1024},
        stop=[],
    )


def _build_app_config(tool_names):
    agent_entity = AgentEntity(
        provider="trustrun-stub",
        model=STUB_MODEL,
        strategy=AgentEntity.Strategy.FUNCTION_CALLING,
        tools=[AgentToolEntity(
            provider_type=ToolProviderType.BUILT_IN,
            provider_id="trustrun",
            tool_name=name,
            tool_parameters={},
        ) for name in tool_names],
        max_iteration=10,
    )
    app_config = AgentChatAppConfig(
        tenant_id=TENANT_ID,
        app_id=APP_ID,
        app_mode=AppMode.AGENT_CHAT,
        app_model_config_from=EasyUIBasedAppModelConfigFrom.ARGS,
        app_model_config_dict={},
        model=ModelConfigEntity(
            provider="trustrun-stub", model=STUB_MODEL,
            parameters={"max_tokens": 1024}, stop=[]),
        prompt_template=PromptTemplateEntity(
            prompt_type=PromptTemplateEntity.PromptType.SIMPLE,
            simple_prompt_template=""),
        agent=agent_entity,
        dataset=None,
    )
    return app_config, agent_entity


def setup():
    """One-time per-process setup: Flask app + SQLite, fakeredis,
    Trustrun tool provider registration. Idempotent."""
    global _SETUP_DONE, _FLASK_CTX
    if _SETUP_DONE:
        return
    from flask import Flask
    from extensions.ext_database import init_app as init_db
    from extensions.ext_redis import redis_client
    from models.base import TypeBase
    from models.engine import db
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    flask_app = Flask("dify-audit69")
    flask_app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + DB_PATH
    flask_app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    init_db(flask_app)
    _FLASK_CTX = flask_app.app_context()
    _FLASK_CTX.push()
    TypeBase.metadata.create_all(
        db.engine,
        tables=[Conversation.__table__, Message.__table__,
                MessageAgentThought.__table__, MessageFile.__table__])
    redis_client.initialize(fakeredis.FakeRedis())
    from trustrun_provider.trustrun import TrustrunToolProvider
    ToolManager.register_hardcoded_provider_class(TrustrunToolProvider)
    providers = list(ToolManager.list_hardcoded_providers())
    names = [p.entity.identity.name for p in providers]
    if "trustrun" not in names:
        raise RuntimeError(
            "trustrun tool provider did not register (have %s)" % names)
    _SETUP_DONE = True


def run_once(task_text, tools, model_log=None, force_first_call=None):
    """Run Dify's real FunctionCallAgentRunner on one task.

    Returns {"result": str, "flagged": bool, "model_log": [...]}.
    Raises when the harness itself fails (the exception propagates
    so the tool-failure-visibility probe can classify it, exactly
    as the n8n adapter does).
    """
    from models.engine import db
    import sqlalchemy
    setup()
    stub = DeterministicStub(task_text, set(tools))
    if force_first_call is not None:
        stub._forced = {
            "name": force_first_call.get("name"),
            "args": force_first_call.get("args") or {},
        }
    _HOLDER["stub"] = stub
    trustrun_bridge.CURRENT_TOOLS = dict(tools)
    conv_id = str(uuid.uuid4())
    msg_id = str(uuid.uuid4())
    conversation = Conversation(
        app_id=APP_ID, mode="chat", name="audit", from_source="api",
        _inputs={}, id=conv_id)
    message = Message(
        app_id=APP_ID, conversation_id=conv_id, query=task_text,
        message="", answer="", from_source="api", _inputs={}, id=msg_id)
    model_instance = _build_model_instance()
    model_conf = _build_model_conf(model_instance)
    app_config, agent_entity = _build_app_config(list(tools.keys()))
    gen_entity = AgentChatAppGenerateEntity(
        task_id=str(uuid.uuid4()),
        app_config=app_config,
        inputs={},
        files=[],
        user_id=USER_ID,
        stream=False,
        invoke_from=InvokeFrom.DEBUGGER,
        model_conf=model_conf,
        conversation_id=conv_id,
        is_new_conversation=True,
    )
    qm = MessageBasedAppQueueManager(
        task_id=str(uuid.uuid4()), user_id=USER_ID,
        invoke_from=InvokeFrom.DEBUGGER, conversation_id=conv_id,
        app_mode=AppMode.AGENT_CHAT.value, message_id=msg_id)
    runner = FunctionCallAgentRunner(
        execution_driver=None,
        session=db.session,
        tenant_id=TENANT_ID,
        application_generate_entity=gen_entity,
        conversation=conversation,
        app_config=app_config,
        model_config=model_conf,
        config=agent_entity,
        queue_manager=qm,
        message=message,
        user_id=USER_ID,
        model_instance=model_instance,
        memory=None,
        prompt_messages=[],
    )
    list(runner.run(session=db.session, message=message,
                    query=task_text))
    final = None
    while not qm._q.empty():
        item = qm._q.get_nowait()
        ev = getattr(item, "event", item)
        if isinstance(ev, QueueMessageEndEvent):
            final = ev.llm_result.message.content
    if final is None:
        # Fallback: the last agent thought's answer in the DB.
        rows = list(db.session.execute(
            sqlalchemy.select(MessageAgentThought).where(
                MessageAgentThought.message_id == msg_id).order_by(
                MessageAgentThought.position.desc())).scalars().all())
        if rows:
            final = rows[0].answer or ""
    log = list(stub.log)
    if model_log is not None:
        model_log.extend(log)
    _HOLDER["stub"] = None
    lowered = (final or "").lower()
    flagged = any(marker in lowered for marker in _FLAG_MARKERS)
    return {"result": final or "", "flagged": flagged, "model_log": log}
