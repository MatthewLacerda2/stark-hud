"""Drive the board from a sentence somebody typed at it.

Everything on this board is put there by a Claude session, and that stays true.
This is a second, much faster way in for small imperative changes — *move the
clock to the left* — which should not have to cost a large model's whole turn.
The prompt goes to one of Google's Flash models with the board's own tools
attached, and whatever it calls is executed here.

**Nothing is re-declared.** The fifty tools already exist in ``hud_mcp`` with
their descriptions and their JSON Schema, and ``MCPServer.list_tools`` hands
them over. A tool added tomorrow is reachable from here the same day with nobody
editing a list, which is the only version of this that stays true.

**And nothing is executed by hand.** A call goes back through the same
``call_tool`` an MCP client comes in by. That keeps one path to the board rather
than two, and it means a widget made from the bar announces itself beside itself
exactly like one made by Claude — the origin in ``services.origin`` hangs off
that method, so it happens here for free and would have to be deliberately
prevented.

Which door that is arrives as an argument. ``hud_mcp`` is a *surface*, the same
height in this stack as ``api``, and neither may import the other or reach down
past ``services`` — so nothing here knows the MCP server exists. It is handed a
`Tooling`, and `main` is where the two surfaces are introduced, because the
composition root is the one place that is allowed to know about both.

The whole thing is one shot. No history, no conversation, no answer rendered
anywhere: the board is the answer, and if a widget moved you saw it move.
"""

import asyncio
import time
from functools import lru_cache
from typing import Any, Protocol

from google import genai
from google.genai import errors, types
from mcp_types import CallToolResult, TextContent, Tool

from core.config import Settings, get_settings
from schemas.command import LEAST_THINKING, CommandCall, CommandRead

# What this model is doing that a Claude session reading the same instructions
# is not. Appended to the server's own instructions rather than replacing them:
# `_INSTRUCTIONS` in `hud_mcp/server.py` is already written for a model that has
# never seen this board and already knows the grid size, and two system prompts
# about one board is two things to be wrong about.
_DRIVING = """
You are driving this board, not discussing it. Somebody at a keyboard typed one
line and is watching the screen; they will see what you did, so there is nothing
to report back and nobody is reading your words.

Call the tools that carry the instruction out. Say nothing else. If the
instruction cannot be carried out with these tools, call nothing — a board that
stays as it was is a clearer answer than a board changed into something nobody
asked for.

You have one turn's worth of patience: do it in as few calls as it takes.

You only have the tools listed with this request. The board's instructions
above mention others — files on a computer, a wake_item to call before slow
work — and those do not exist for you: you cannot see the computer this board
runs on, and nothing you do takes long enough to announce.
"""

# Never sent to a typed instruction, whatever their annotations say. `wake_item`
# is the pulse a Claude session sends before going away to think for a while;
# a Flash model answers in a moment, so from here it is a round trip that shows
# the room a widget waking up for nothing.
_NOT_FOR_TYPING = frozenset({"wake_item"})


class Tooling(Protocol):
    """Whatever can say what the board can do, and then do one of those things.

    An MCP server is exactly this shape, which is the point: `main` hands the
    real one over and nothing in this module has to import it. It also means
    this can be driven by a stand-in that never talks to anything, which is the
    only way the loop below is testable without an account.
    """

    #: What the model is told before it sees the prompt — the board's own
    #: instructions, already written for a model that has never seen it.
    instructions: str | None

    async def list_tools(self) -> list[Tool]:
        """Everything the board can be asked to do."""
        ...

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        """Do one of them, and answer the way that tool answers."""
        ...


class CommandError(Exception):
    """Something stopped a typed instruction, in one sentence for the bar.

    The message is shown to a person standing at a keyboard, so it says what to
    do about it. Same bargain `services.speech` makes with the voice: a vendor's
    401 means either a bad key or a good key missing a permission, and telling
    somebody the wrong one sends them to stare at a credential that is fine.
    """


@lru_cache(maxsize=1)
def _client(key: str) -> genai.Client:
    """The Gemini client, built once and kept.

    Keyed on the key so a test can hand it a different one and get a different
    client, and so nothing here holds a client built from a key that has since
    changed.
    """
    return genai.Client(api_key=key)


def typeable(tools: list[Tool]) -> list[Tool]:
    """The tools a typed instruction may use: the ones that need only the board.

    A model behind this bar sees the board and the sentence and nothing else. It
    has never seen the computer the board runs on, so a tool that takes a path
    on that computer — a picture, a film, a 3D file, a background — is a tool it
    can only guess at, and a guessed path is a widget that says "file not
    found" on a television. Those tools mark themselves with MCP's own
    `open_world_hint` where they are defined (`hud_mcp.common.ON_HOST`), so the
    rule lives with the tool rather than in a list here that goes stale the
    day somebody adds a seventh.

    Claude keeps every tool. This is not a second catalogue, it is the same one
    with the doors this model cannot walk through left shut.
    """
    return [
        tool
        for tool in tools
        if tool.name not in _NOT_FOR_TYPING
        and not (tool.annotations and tool.annotations.open_world_hint)
    ]


def declarations(tools: list[Tool]) -> list[types.FunctionDeclaration]:
    """Every MCP tool it is given, as something Gemini can call.

    `parameters_json_schema` and not `parameters`: the latter takes Gemini's own
    OpenAPI subset, and every optional argument on this board is `X | None` in
    Pydantic, which serialises as ``anyOf: [{type: X}, {type: null}]``. That is
    JSON Schema and not the subset, so the schema goes across as written and the
    conversion stays a rename of three fields rather than a translator nobody
    can debug from a wrong answer on a television.

    The descriptions come across whole. They are long — the fifty of them are
    about forty thousand characters, and with the schemas roughly sixteen
    thousand tokens on every prompt — and they are the entire reason a model
    that has never seen this board can use it. Trimming them for Gemini
    specifically is a real idea and a measurement should decide it, not a guess
    made while writing this.
    """
    return [
        types.FunctionDeclaration(
            name=tool.name,
            description=tool.description or "",
            parameters_json_schema=tool.input_schema,
        )
        for tool in tools
    ]


def _thinking(model: str) -> types.ThinkingConfig | None:
    """Turn the thinking dial as far down as this model allows.

    Left alone, these models stop and think before answering, which on a menu
    whose whole purpose is speed makes them slower than they need to be. The
    floor is per model (`LEAST_THINKING`), and going under it is a 400, not a
    quiet round-up.
    """
    level = LEAST_THINKING.get(model)
    if level is None:
        return None
    return types.ThinkingConfig(thinking_level=types.ThinkingLevel(level))


def _said(result: CallToolResult) -> str:
    """The line a tool answered with.

    Every tool on this board returns one sentence of plain English, written to
    be read by the model that called it — "Added note a1b2c3 at (4,2)", or the
    refusal saying what is free instead. Handed back untouched: it is the honest
    record of what happened, and a refusal has to read like one.
    """
    lines = [part.text for part in result.content if isinstance(part, TextContent)]
    return " ".join(line.strip() for line in lines if line.strip()) or "(nothing said)"


async def _call(board: Tooling, name: str, arguments: dict[str, Any]) -> str:
    """Run one tool the model asked for, through the door every client uses."""
    result = await board.call_tool(name, arguments)
    if not isinstance(result, CallToolResult):
        # Elicitation: no tool on this board asks a question back, and there is
        # nobody in the loop to answer one if it did.
        return f"{name} asked for input, which this path cannot give it"
    return _said(result)


def _config(
    settings: Settings, board: Tooling, model: str, tools: list[Tool]
) -> types.GenerateContentConfig:
    """Everything the model is told before it sees the prompt."""
    return types.GenerateContentConfig(
        system_instruction=(board.instructions or "") + _DRIVING,
        tools=[types.Tool(function_declarations=declarations(tools))],
        # The SDK's own loop only knows how to call Python functions it was
        # handed. Ours are MCP tools reached through `call_tool`, so the loop is
        # below and this makes sure there is not a second one underneath it.
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        # Deliberately AUTO rather than ANY. ANY forces a call, and the honest
        # answer to "what colour is the clock" is no call at all — a board
        # changed into something nobody asked for is worse than one that did not
        # move.
        tool_config=types.ToolConfig(
            function_calling_config=types.FunctionCallingConfig(
                mode=types.FunctionCallingConfigMode.AUTO
            )
        ),
        thinking_config=_thinking(model),
        temperature=0.0,
        max_output_tokens=settings.GEMINI_MAX_OUTPUT_TOKENS,
    )


async def _rounds(
    settings: Settings, board: Tooling, model: str, prompt: str, tools: list[Tool]
) -> list[CommandCall]:
    """Ask, run whatever came back, ask again with the answers. Until it stops.

    A model that calls three tools at once gets all three run before it is asked
    anything further, which is one round trip instead of three — and reordering
    them would be inventing an order the model did not ask for. Tools on this
    board are ordinary functions over one dict, so running them in the order
    they arrived is both correct and what the model expects.

    The loop ends the moment a turn asks for nothing, which is the normal exit:
    the work is done and there is nothing left to say. `GEMINI_MAX_ROUNDS` is
    the other exit, and it is a ceiling rather than a target — anything typed at
    this board is one or two calls, and a model still going on the fourth turn
    is looping rather than working.
    """
    client = _client(settings.GEMINI_API_KEY)
    config = _config(settings, board, model, tools)
    said: list[types.Content] = [
        types.Content(role="user", parts=[types.Part.from_text(text=prompt)])
    ]
    done: list[CommandCall] = []

    for _ in range(settings.GEMINI_MAX_ROUNDS):
        answer = await client.aio.models.generate_content(model=model, contents=said, config=config)
        wanted = answer.function_calls or []
        if not wanted:
            return done

        # The model's own turn goes back in before the results, or the next turn
        # sees answers to questions it cannot see itself having asked. Exactly
        # as it came, not rebuilt from the calls: a thinking model signs its
        # function calls (`thought_signature`), and Google refuses the next
        # round with a 400 if the signature is missing or altered.
        said.append(_turn(answer))
        answers: list[types.Part] = []
        for call in wanted:
            name = call.name or ""
            told = await _call(board, name, dict(call.args or {}))
            done.append(CommandCall(tool=name, said=told))
            answers.append(types.Part.from_function_response(name=name, response={"said": told}))
        said.append(types.Content(role="user", parts=answers))

    return done


def _turn(answer: types.GenerateContentResponse) -> types.Content:
    """The model's turn, untouched, to be sent back with the tool results.

    Only reached after `function_calls` found calls, which it reads from this
    same first candidate, so the content is there.
    """
    return (answer.candidates or [types.Candidate()])[0].content or types.Content(role="model")


async def run(prompt: str, board: Tooling, model: str | None = None) -> CommandRead:
    """Carry out one typed instruction, and say what it did.

    Raises `CommandError` with one sentence when it could not start or could not
    finish — no key, a key the vendor refused, or a model that took longer than
    anybody standing at a keyboard will wait.
    """
    settings = get_settings()
    if not settings.GEMINI_API_KEY:
        raise CommandError(
            "No Gemini key, so the board cannot be typed at. Put GEMINI_API_KEY in .env "
            "and restart the backend; everything else on the board works without it."
        )

    chosen = model or settings.GEMINI_MODEL
    tools = typeable(await board.list_tools())
    began = time.monotonic()
    try:
        async with asyncio.timeout(settings.GEMINI_TIMEOUT_SECONDS):
            calls = await _rounds(settings, board, chosen, prompt, tools)
    except TimeoutError as exc:
        raise CommandError(
            f"{chosen} did not answer within {settings.GEMINI_TIMEOUT_SECONDS:g} seconds. "
            f"Nothing was left half-done that it had not already finished; try again, or "
            f"pick a smaller model."
        ) from exc
    except errors.ClientError as exc:
        raise CommandError(_refused(exc, chosen)) from exc
    except errors.ServerError as exc:
        raise CommandError(
            f"Google could not answer for {chosen} just now ({exc.code}). This one is "
            f"theirs rather than ours — try again, or pick another model."
        ) from exc

    return CommandRead(
        model=chosen,
        calls=calls,
        took_ms=round((time.monotonic() - began) * 1000),
    )


def _refused(exc: errors.ClientError, model: str) -> str:
    """Turn the vendor's refusal into the one thing to go and do about it.

    The three that actually happen mean three different fixes, and a single
    "the API rejected the request" sends somebody to check the wrong one — the
    same trap `services.speech` documents about ElevenLabs' two identical 401s.
    """
    if exc.code == 401 or exc.code == 403:
        return (
            "Google refused the Gemini key. Either it is wrong, or it has not had the "
            "Generative Language API enabled for its project — check the key in .env first."
        )
    if exc.code == 404:
        return (
            f"Google has no model called {model}. Model names change; check the current "
            f"list at ai.google.dev before adding one here."
        )
    if exc.code == 429:
        return (
            "The Gemini account is out of quota for now — either the free tier's rate "
            "limit, or the project has no billing. The board is untouched."
        )
    return f"Gemini refused the instruction ({exc.code}): {exc.message}"
