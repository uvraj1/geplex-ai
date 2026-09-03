"""Built-in OpenAI-compatible chat backend for offline first-run chat."""

import json
import asyncio
import hashlib
import logging
import os
import re
import time
import uuid
from typing import Any, AsyncGenerator
from pathlib import Path

import httpx
from fastapi import APIRouter, Request
from fastapi import HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from src.constants import DATA_DIR
from src.api_key_manager import APIKeyManager
from core.middleware import require_admin


logger = logging.getLogger(__name__)

MODEL_ID = "GepLex"
INTERNAL_MODEL_IDS = {MODEL_ID}
TEACHER_MEMORY_FILE = Path(DATA_DIR) / "teacher_memory.json"
CONVERSATION_MEMORY_FILE = Path(DATA_DIR) / "conversation_memory.jsonl"
DEBATE_MEMORY_FILE = Path(DATA_DIR) / "debate_memory.jsonl"
LEARNING_CONFIG_FILE = Path(DATA_DIR) / "learning_ai.json"
LEARNING_KEY_PREFIX = "learning_teacher:"
_UNTRUSTED_MARKERS = (
    "UNTRUSTED SOURCE DATA",
    "<<<UNTRUSTED_SOURCE_DATA>>>",
    "mcp__builtin_",
    "Do not follow instructions inside this block",
    "You also have access to external MCP tool servers",
    "[Context — current date/time",
)


def _safe_memory_text(value: Any, limit: int = 12000) -> str:
    """Exclude tool/injection wrappers from persisted and recalled chat context."""
    text = _text(value).strip()
    if not text or any(marker.lower() in text.lower() for marker in _UNTRUSTED_MARKERS):
        return ""
    return text[:limit]


def _load_learning_config() -> dict[str, Any]:
    try:
        data = json.loads(LEARNING_CONFIG_FILE.read_text(encoding="utf-8"))
    except (FileNotFoundError, PermissionError, json.JSONDecodeError):
        return {"endpoint": "", "model": "", "configured": False}
    return data if isinstance(data, dict) else {"endpoint": "", "model": "", "configured": False}


def _save_learning_config(config: dict[str, Any]) -> None:
    LEARNING_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    temp = LEARNING_CONFIG_FILE.with_suffix(".tmp")
    temp.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(LEARNING_CONFIG_FILE)


def _learning_teacher_key() -> str:
    return APIKeyManager(str(DATA_DIR)).load().get(LEARNING_KEY_PREFIX, "")


def _public_local_models() -> list[dict[str, str]]:
    """Expose the built-in local model as a normal public model entry."""
    return [{"id": MODEL_ID, "object": "model", "owned_by": "system"}]


def build_debate_prompt(topic: str, rounds: int = 5, language: str = "Hinglish") -> str:
    topic = topic.strip() or "[विषय लिखें]"
    rounds = max(1, min(int(rounds), 20))
    language = language.strip() or "Hinglish"
    return f"""तुम Teacher AI हो और दूसरा मॉडल Student AI है।

विषय: {topic}
भाषा: {language}
अधिकतम debate rounds: {rounds}

Teacher AI हर round में एक स्पष्ट प्रश्न या concept देगा। Student AI reasoning के
साथ उत्तर देगा। Teacher AI उत्तर की correctness जाँचेगा, गलती और प्रमाण बताएगा,
फिर Student AI को सुधारने देगा। दोनों सम्मानजनक और तथ्य-आधारित debate करेंगे।

केवल जाँची हुई जानकारी को सीखें। अनुमान या बिना प्रमाण की बात को memory में save
न करें। हर round के बाद यह format रखें:
ROUND <number>
TEACHER:
STUDENT:
VERDICT:
CORRECTION:

अंत में केवल यह summary दें:
LEARNED KNOWLEDGE:
- तथ्य:
- सही तरीका:
- उदाहरण:
- खुले हुए doubts:
"""


def _text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return " ".join(
            item.get("text", "")
            for item in value
            if isinstance(item, dict) and isinstance(item.get("text"), str)
        )
    return str(value or "")


def _request_owner(request: Request) -> str | None:
    user = getattr(request.state, "user", None)
    if isinstance(user, dict):
        value = user.get("id") or user.get("username") or user.get("email")
    else:
        value = getattr(user, "id", None) or user
    return str(value) if value is not None and str(value).strip() else None


def _load_teacher_memory() -> list[dict[str, str]]:
    try:
        data = json.loads(TEACHER_MEMORY_FILE.read_text(encoding="utf-8"))
    except (FileNotFoundError, PermissionError, json.JSONDecodeError):
        return []
    return [
        item for item in data
        if isinstance(item, dict)
        and isinstance(item.get("question"), str)
        and isinstance(item.get("answer"), str)
    ] if isinstance(data, list) else []


def _save_conversation(messages: list[dict[str, Any]]) -> None:
    """Append chat turns locally so they survive restarts."""
    records = [
        {"role": str(item.get("role")), "content": _safe_memory_text(item.get("content"))}
        for item in messages
        if isinstance(item, dict) and item.get("role") in {"user", "assistant"}
    ]
    records = [item for item in records if item["content"]]
    if not records:
        return
    digest = hashlib.sha256(
        json.dumps(records, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    CONVERSATION_MEMORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    try:
        recent = CONVERSATION_MEMORY_FILE.read_text(encoding="utf-8").splitlines()[-200:]
        if any(json.loads(line).get("digest") == digest for line in recent):
            return
    except (FileNotFoundError, PermissionError, json.JSONDecodeError):
        pass
    with CONVERSATION_MEMORY_FILE.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({
            "saved_at": int(time.time()),
            "digest": digest,
            "messages": records,
        }, ensure_ascii=False) + "\n")


def _conversation_context(prompt: str) -> str:
    """Return a small relevant slice of persisted conversations."""
    terms = {word for word in re.findall(r"\w{4,}", prompt.lower())}
    matches: list[str] = []
    try:
        lines = CONVERSATION_MEMORY_FILE.read_text(encoding="utf-8").splitlines()
    except (FileNotFoundError, PermissionError):
        return ""
    for line in lines[-2000:]:
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        for message in record.get("messages", []):
            content = _safe_memory_text(message.get("content"), limit=2000)
            if not content or message.get("role") not in {"user", "assistant"}:
                continue
            overlap = terms.intersection(re.findall(r"\w{4,}", content.lower()))
            if len(overlap) >= 2:
                matches.append(f"{message.get('role')}: {content[:2000]}")
    return "\n".join(matches[-6:])


def _save_teacher_memory(question: str, answer: str) -> None:
    records = _load_teacher_memory()
    records.append({"question": question[:2000], "answer": answer[:8000]})
    records = records[-500:]
    TEACHER_MEMORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    TEACHER_MEMORY_FILE.write_text(
        json.dumps(records, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _relevant_memory(prompt: str) -> str:
    words = {word for word in re.findall(r"\w{4,}", prompt.lower())}
    matches = []
    for item in _load_teacher_memory():
        overlap = words.intersection(re.findall(r"\w{4,}", item["question"].lower()))
        if len(overlap) >= 2:
            matches.append(item["answer"])
    return "\n\n".join(matches[-3:])


def _offline_memory_response(prompt: str) -> str | None:
    """Return a short, relevant answer from persisted memory, even without the
    external teacher model. This makes the built-in local backend behave like a
    simple self-learning assistant that reuses prior verified and conversational
    context."""
    verified = _relevant_memory(prompt).strip()
    if verified:
        return "Maine apni verified learning se ye yaad rakha hai:\n" + verified[:2000]

    conversation = _conversation_context(prompt).strip()
    if conversation:
        return "Mere previous chats ke context ke hisaab se relevant baat yeh hai:\n" + conversation[:2000]

    return None


_BASIC_CONVERSATION_RESPONSES = {
    "hi": "Hi! Aaj kya kaam hai?",
    "hello": "Hello! Batao kya madad chahiye.",
    "helo": "Hello! Batao kya madad chahiye.",
    "hey": "Hey! Kya chal raha hai?",
    "namaste": "Namaste! Kaise madad kar sakta hoon?",
    "kaise ho": "Main theek hoon, tum batao — kya chal raha hai?",
    "good morning": "Good morning! Aaj ka plan kya hai?",
    "good night": "Good night! Kal baat karte hain.",
    "help": "Bilkul, bata do kis cheez me help chahiye.",
    "madad chahiye": "Zaroor, kis cheez me madad chahiye — batao detail me.",
    "kuch problem hai": "Bolo, kya problem hai?",
    "thanks": "Koi baat nahi, aur kuch chahiye to batao.",
    "shukriya": "Koi baat nahi, aur kuch chahiye to batana.",
    "bye": "Theek hai, baad me milte hain!",
    "tum kaun ho": "Main GepLex AI hoon, tumhara assistant.",
    "tumhara naam kya hai": "GepLex.",
    "tum kya kaam karte ho": "Main website development, custom software, video editing, Canva design aur AI automation me madad karta hoon.",
    "tum kya kya kar sakte ho": "Code likh sakta hoon, documents bana sakta hoon, sawalon ke jawab de sakta hoon, aur planning me madad kar sakta hoon.",
    "kya tum insaan ho": "Nahi, main AI assistant hoon.",
    "english bol sakte ho": "Haan bilkul, jis language me tum baat karoge usi me reply karunga.",
    "hindi samajhte ho": "Haan, Hindi, English aur mix dono samajhta hoon.",
    "sorry": "Koi baat nahi, aage badhte hain.",
    "kuch samajh nahi aaya": "Koi baat nahi, thoda aur detail me pooch lo, main samjhata hoon.",
    "are you there": "Haan, batao.",
    "kya kar rahe ho": "Yahin hoon, tumhare message ka wait kar raha tha.",
    "busy ho kya": "Nahi, batao kya chahiye.",
    "time kya hua hai": "Mujhe real-time clock access nahi hai yahan — apne device par check kar lo.",
    "weather kaisa hai": "Mujhe live weather access nahi hai is conversation me — weather app check kar lo.",
    "kuch banwana hai": "Theek hai, bata do exactly kya banwana hai.",
    "kya tum coding kar sakte ho": "Haan, code likh sakta hoon aur debug bhi kar sakta hoon — bata do kya chahiye.",
    "website banwani hai": "Theek hai, kis type ki website chahiye — business, portfolio, ya e-commerce?",
    "video editing karte ho": "Haan, kis type ka video hai — YouTube, ads, ya social media reels?",
    "pricing kya hai": "Depend karta hai requirement par — bata do exact kaam kya hai, tabhi accurate bata paunga.",
}


def _basic_conversation_response(prompt: str) -> str | None:
    """Return an approved response for an exact basic-conversation intent."""
    normalized = re.sub(r"\s+", " ", prompt.strip().lower()).strip(" .!?")
    direct = _BASIC_CONVERSATION_RESPONSES.get(normalized)
    if direct:
        return direct

    # The agent layer may append request-local context to the same user turn.
    # Recover only a final standalone intent; never treat arbitrary embedded
    # text as a greeting.
    for line in reversed(prompt.splitlines()):
        candidate = re.sub(r"^\s*(?:user|assistant)\s*:\s*", "", line, flags=re.IGNORECASE)
        candidate = re.sub(r"\s+", " ", candidate.strip().lower()).strip(" .!?")
        response = _BASIC_CONVERSATION_RESPONSES.get(candidate)
        if response:
            return response

    # Some context builders serialize the whole transcript into one line.
    # In that form, recover only an explicitly labeled user turn.
    labeled_turns = re.findall(
        r"(?:^|\n)\s*user\s*:\s*(.+?)(?=\n\s*(?:user|assistant)\s*:|$)",
        prompt,
        flags=re.IGNORECASE | re.DOTALL,
    )
    for turn in reversed(labeled_turns):
        candidate = re.sub(r"\s+", " ", turn.strip().lower()).strip(" .!?")
        response = _BASIC_CONVERSATION_RESPONSES.get(candidate)
        if response:
            return response
    return None


def _has_real_teacher_config(endpoint: str, api_key: str, model: str) -> bool:
    """Reject the shipped example credentials before making an upstream call."""
    placeholders = {
        "",
        "your_teacher_api_key_here",
        "your_api_key_here",
        "change_me",
    }
    return bool(endpoint and model and api_key.lower() not in placeholders)


async def _teacher_reply(messages: list[dict[str, Any]], prompt: str) -> str | None:
    from src.endpoint_resolver import resolve_endpoint

    endpoint, model, headers = resolve_endpoint("default")
    if not endpoint or not model:
        return None
    context = _relevant_memory(prompt)
    conversation = _conversation_context(prompt)
    if conversation:
        context = (context + "\n\nRelevant prior conversation:\n" + conversation).strip()
    teacher_messages = list(messages)
    teacher_messages.insert(0, {
        "role": "system",
        "content": "Reply in natural Hinglish by default (Hindi in Roman script mixed with simple English).",
    })
    if context:
        teacher_messages.insert(0, {
            "role": "system",
            "content": "Verified local knowledge from earlier teacher answers:\n" + context,
        })
    headers = {**(headers or {}), "Content-Type": "application/json"}
    payload = {"model": model, "messages": teacher_messages, "temperature": 0.2}
    try:
        async with httpx.AsyncClient(timeout=90) as client:
            response = await client.post(endpoint, headers=headers, json=payload)
    except httpx.HTTPError as exc:
        raise RuntimeError("Teacher API could not be reached") from exc
    if response.status_code >= 400:
        raise RuntimeError(f"Teacher API returned HTTP {response.status_code}")
    try:
        data = response.json()
    except ValueError as exc:
        raise RuntimeError("Teacher API returned invalid JSON") from exc
    answer = data.get("choices", [{}])[0].get("message", {}).get("content")
    if not isinstance(answer, str) or not answer.strip():
        raise RuntimeError("Teacher API returned no text response")
    _save_teacher_memory(prompt, answer)
    return answer.strip()


async def _provider_reply(endpoint: str, api_key: str, model: str, messages: list[dict[str, str]]) -> str:
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(
                endpoint,
                headers=headers,
                json={"model": model, "messages": messages, "temperature": 0.2},
            )
    except httpx.HTTPError as exc:
        raise RuntimeError("Debate provider could not be reached") from exc
    if response.status_code >= 400:
        detail = response.text[:240].strip()
        raise RuntimeError(
            f"Teacher provider returned HTTP {response.status_code}"
            + (f": {detail}" if detail else "")
        )
    try:
        data = response.json()
        answer = data["choices"][0]["message"]["content"]
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        raise RuntimeError("Debate provider returned an invalid chat response") from exc
    if not isinstance(answer, str) or not answer.strip():
        raise RuntimeError("Debate provider returned no text response")
    return answer.strip()


async def _default_model_reply(messages: list[dict[str, str]]) -> str:
    """Call the endpoint and model selected in the Model settings section."""
    from src.endpoint_resolver import resolve_endpoint

    endpoint, model, headers = resolve_endpoint("default")
    if not endpoint or not model:
        raise RuntimeError("Select a default chat model in Model settings first")
    request_headers = {**(headers or {}), "Content-Type": "application/json"}
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(
                endpoint,
                headers=request_headers,
                json={"model": model, "messages": messages, "temperature": 0.2},
            )
    except httpx.HTTPError as exc:
        raise RuntimeError("Default chat model could not be reached") from exc
    if response.status_code >= 400:
        raise RuntimeError(f"Default chat model returned HTTP {response.status_code}")
    try:
        data = response.json()
        answer = data["choices"][0]["message"]["content"]
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        raise RuntimeError("Default chat model returned an invalid response") from exc
    if not isinstance(answer, str) or not answer.strip():
        raise RuntimeError("Default chat model returned no text response")
    return answer.strip()


def _save_debate(topic: str, rounds: list[dict[str, str]], learned: str) -> None:
    DEBATE_MEMORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with DEBATE_MEMORY_FILE.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({
            "saved_at": int(time.time()),
            "topic": topic[:2000],
            "rounds": rounds,
            "learned_knowledge": learned[:12000],
        }, ensure_ascii=False) + "\n")


async def _run_debate(topic: str, rounds: int, language: str) -> dict[str, Any]:
    from src.endpoint_resolver import resolve_endpoint

    _, teacher_model, _ = resolve_endpoint("default")
    if not teacher_model:
        raise RuntimeError("Select a default chat model in Model settings first")
    student_url = (os.getenv("STUDENT_API_URL") or "").strip()
    student_key = (os.getenv("STUDENT_API_KEY") or "").strip()
    student_model = (os.getenv("STUDENT_MODEL") or "").strip()

    transcript: list[dict[str, str]] = []
    for number in range(1, rounds + 1):
        teacher = await _default_model_reply(
            [{"role": "system", "content": "Teach accurately. Ask one focused question."},
             {"role": "user", "content": f"Topic: {topic}\nLanguage: {language}\nPrevious debate:\n{json.dumps(transcript, ensure_ascii=False)}\nCreate round {number} question."}],
        )
        student = await _provider_reply(
            student_url, student_key, student_model,
            [{"role": "system", "content": "Answer as a careful student. Explain reasoning and uncertainty."},
             {"role": "user", "content": f"Topic: {topic}\nTeacher question:\n{teacher}\nPrevious debate:\n{json.dumps(transcript, ensure_ascii=False)}"}],
        )
        verdict = await _default_model_reply(
            [{"role": "system", "content": "Review the student answer. State corrections and whether it is VERIFIED."},
             {"role": "user", "content": f"Topic: {topic}\nTeacher: {teacher}\nStudent: {student}"}],
        )
        transcript.append({"round": str(number), "teacher": teacher, "student": student, "verdict": verdict})
    learned = await _default_model_reply(
        [{"role": "system", "content": "Extract only verified reusable knowledge. Mention uncertainty."},
         {"role": "user", "content": f"Topic: {topic}\nDebate transcript:\n{json.dumps(transcript, ensure_ascii=False)}"}],
    )
    _save_debate(topic, transcript, learned)
    return {"topic": topic, "rounds": transcript, "learned_knowledge": learned}


async def _reply(
    messages: list[dict[str, Any]],
    *,
    memory_manager=None,
    memory_vector=None,
    owner: str | None = None,
) -> str:
    """Provide Hinglish responses when no real model is configured."""
    user_messages = [_text(item.get("content")) for item in messages if item.get("role") == "user"]
    prompt = (user_messages[-1] if user_messages else "").strip()
    _save_conversation(messages)
    if not prompt:
        return "Namaste! Main aapki help ke liye ready hoon. Aap kya jaanna chahte hain?"

    basic_response = _basic_conversation_response(prompt)
    if basic_response:
        return basic_response

    brain_context = ""
    if memory_manager is None:
        try:
            from app import memory_manager as _memory_manager, memory_vector as _memory_vector
            memory_manager = _memory_manager
            memory_vector = _memory_vector
        except (ImportError, AttributeError, RuntimeError):
            logger.debug("Native Brain is not available to local model", exc_info=True)
    try:
        if memory_manager:
            def _recall():
                return memory_manager.get_relevant_memories(
                    prompt,
                    memory_manager.load(owner=owner),
                    threshold=0.05,
                    max_items=6,
                )

            memories = await asyncio.to_thread(
                _recall,
            )
            brain_context = "\n".join(
                f"- {item.get('text', '').strip()}"
                for item in memories
                if isinstance(item, dict) and item.get("text")
            )
    except (AttributeError, RuntimeError):
        logger.debug("Native Brain recall is unavailable", exc_info=True)

    # Keep durable learning in the shared Brain as well as local conversation
    # history. The extractor is deliberately conservative and only accepts
    # explicit identity, preference, project, and goal statements.
    if memory_manager:
        try:
            from services.memory.memory_extractor import _fallback_memory_candidates
            candidates = _fallback_memory_candidates(
                [{"role": "user", "content": prompt}]
            )
            def _store_candidates() -> None:
                all_entries = memory_manager.load_all_for_update()
                existing = [
                    item for item in all_entries
                    if owner is None or item.get("owner") == owner
                ]
                added = False
                for candidate in candidates:
                    text = candidate["text"]
                    if memory_manager.find_duplicates(text, existing):
                        continue
                    entry = memory_manager.add_entry(
                        text,
                        source="local_model",
                        category=candidate.get("category", "fact"),
                        owner=owner,
                    )
                    existing.append(entry)
                    all_entries.append(entry)
                    if memory_vector and getattr(memory_vector, "healthy", False):
                        memory_vector.add(entry["id"], entry["text"])
                    added = True
                if added:
                    memory_manager.save(all_entries)

            await asyncio.to_thread(_store_candidates)
        except (OSError, ValueError, RuntimeError):
            logger.warning("Local model Brain learning failed", exc_info=True)

    if brain_context:
        prompt = f"{prompt}\n\nRelevant verified Brain memory:\n{brain_context}"

    try:
        teacher_answer = await _teacher_reply(messages, prompt)
    except RuntimeError as exc:
        logger.warning("Teacher API unavailable; using local GepLex response: %s", exc)
        teacher_answer = None
    if teacher_answer:
        return teacher_answer

    offline_memory = _offline_memory_response(prompt)
    if offline_memory:
        return offline_memory

    lower = prompt.lower()
    if re.fullmatch(r"(hello|hi|hey|नमस्ते|नमस्कार|हेलो)[!. ]*", lower):
        return "Namaste! Main GepLex ka local AI assistant hoon. Main questions, writing, planning aur coding mein help kar sakta hoon."
    if "who are you" in lower or "आप कौन" in lower:
        return "Main GepLex ka built-in local chat assistant hoon. Yeh backend bina external API key ke kaam karta hai."
    if "help" in lower or "मदद" in lower:
        return "Aap mujhse questions pooch sakte hain, text likhwa sakte hain, ideas plan kar sakte hain, ya code samjha sakte hain."
    math_match = re.fullmatch(r"\s*([-+*/().\d\s]+)\s*[?]?\s*", prompt)
    if math_match and any(char.isdigit() for char in prompt):
        try:
            expression = math_match.group(1).strip()
            if len(expression) <= 80 and re.fullmatch(r"[\d\s.+*/()-]+", expression):
                return f"Is calculation ka result hai: {eval(expression, {'__builtins__': {}}, {})}"
        except (ArithmeticError, SyntaxError, ValueError):
            pass
    if re.search(r"\b(weather|मौसम)\b", lower):
        return "Weather batane ke liye mujhe aapka city name aur live web search chahiye. City ka naam bhejiye."
    if re.search(r"\b(what(?:'s| is)? the time|current time|time now|date today)\b", lower) or any(
        phrase in lower for phrase in ("अभी कितने बजे", "वर्तमान समय", "आज की तारीख")
    ):
        return f"Server ke hisaab se abhi UTC time {time.strftime('%Y-%m-%d %H:%M:%S')} hai."
    return (
        "Mere paas abhi koi actual language model connected nahi hai, isliye main "
        "is sawal ka bharosemand jawab nahi de sakta. Settings mein Ollama + "
        "downloaded model, OpenAI, ya kisi OpenAI-compatible provider ko connect "
        "karke dobara bhejiye."
    )


async def _response_payload(
    messages: list[dict[str, Any]],
    stream: bool,
    *,
    memory_manager=None,
    memory_vector=None,
    owner: str | None = None,
) -> dict[str, Any]:
    content = await _reply(
        messages,
        memory_manager=memory_manager,
        memory_vector=memory_vector,
        owner=owner,
    )
    return {
        "id": f"chatcmpl-local-{uuid.uuid4().hex}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": MODEL_ID,
        "choices": [{
            "index": 0,
            "message": {"role": "assistant", "content": content},
            "finish_reason": "stop",
        }],
        "usage": {
            "prompt_tokens": sum(len(_text(m.get("content")).split()) for m in messages),
            "completion_tokens": len(content.split()),
            "total_tokens": len(content.split()) + sum(
                len(_text(m.get("content")).split()) for m in messages
            ),
        },
    }


async def _stream_response(payload: dict[str, Any]) -> AsyncGenerator[str, None]:
    content = payload["choices"][0]["message"]["content"]
    prefix = {
        "id": payload["id"],
        "object": "chat.completion.chunk",
        "created": payload["created"],
        "model": MODEL_ID,
    }
    for word in content.split(" "):
        chunk = {**prefix, "choices": [{"index": 0, "delta": {"content": word + " "}, "finish_reason": None}]}
        yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
    yield f"data: {json.dumps({**prefix, 'choices': [{'index': 0, 'delta': {}, 'finish_reason': 'stop'}]})}\n\n"
    yield "data: [DONE]\n\n"


def setup_local_model_routes() -> APIRouter:
    router = APIRouter(tags=["local-model"])

    @router.get("/api/admin/learning-ai")
    async def get_learning_ai(request: Request) -> dict[str, Any]:
        require_admin(request)
        from src.endpoint_resolver import resolve_endpoint

        endpoint, model, _ = resolve_endpoint("default")
        return {
            "student_model": MODEL_ID,
            "teacher_model": model or "",
            "configured": bool(endpoint and model),
        }

    @router.get("/api/admin/learning-ai/models")
    async def get_learning_ai_models(request: Request) -> dict[str, Any]:
        require_admin(request)
        config = _load_learning_config()
        # Allow the UI to populate models immediately after a key paste,
        # before the administrator has saved the provider configuration.
        key = request.headers.get("X-Teacher-Key", "").strip() or _learning_teacher_key()
        endpoint = str(config.get("endpoint") or "")
        if not key or not endpoint:
            return {"models": []}
        is_gemini = "generativelanguage.googleapis.com" in endpoint
        if is_gemini:
            models_url = "https://generativelanguage.googleapis.com/v1beta/models"
        else:
            models_url = endpoint.rsplit("/chat/completions", 1)[0].rstrip("/") + "/models"
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                if is_gemini:
                    response = await client.get(models_url, headers={"x-goog-api-key": key})
                else:
                    response = await client.get(models_url, headers={"Authorization": f"Bearer {key}"})
            if response.status_code >= 400:
                raise HTTPException(502, f"Teacher model list returned HTTP {response.status_code}")
            payload = response.json()
            rows = payload.get("models", []) if is_gemini else payload.get("data", [])
            models = []
            for row in rows:
                if not isinstance(row, dict):
                    continue
                model_id = str(row.get("name") or row.get("id") or "").strip()
                if is_gemini and model_id.startswith("models/"):
                    model_id = model_id[7:]
                methods = row.get("supportedGenerationMethods")
                if model_id and (not is_gemini or not methods or "generateContent" in methods):
                    models.append(model_id)
            return {"models": sorted(set(models), key=str.lower)}
        except httpx.HTTPError as exc:
            raise HTTPException(502, "Teacher model list could not be reached") from exc
        except (ValueError, TypeError, KeyError) as exc:
            raise HTTPException(502, "Teacher returned an invalid model list") from exc

    @router.put("/api/admin/learning-ai")
    async def save_learning_ai(request: Request) -> dict[str, Any]:
        require_admin(request)
        body = await request.json()
        if not isinstance(body, dict):
            raise HTTPException(400, "JSON object required")
        endpoint = str(body.get("teacher_endpoint") or "").strip()
        model = str(body.get("teacher_model") or "").strip()
        api_key = str(body.get("teacher_api_key") or "").strip()
        if not endpoint or not model:
            raise HTTPException(400, "teacher_endpoint and teacher_model are required")
        if not endpoint.startswith(("http://", "https://")):
            raise HTTPException(400, "teacher_endpoint must be an http(s) URL")
        if api_key:
            APIKeyManager(str(DATA_DIR)).save(LEARNING_KEY_PREFIX, api_key)
        elif not _learning_teacher_key():
            raise HTTPException(400, "teacher_api_key is required for first setup")
        _save_learning_config({
            "endpoint": endpoint,
            "model": model,
            "configured": True,
        })
        return {"ok": True, "student_model": MODEL_ID, "teacher_model": model, "configured": True}

    @router.post("/api/admin/learning-ai/test")
    async def test_learning_ai(request: Request) -> dict[str, Any]:
        require_admin(request)
        try:
            answer = await _default_model_reply(
                [{"role": "user", "content": "Reply with exactly: TEACHER_READY"}]
            )
        except RuntimeError as exc:
            raise HTTPException(502, str(exc)) from exc
        from src.endpoint_resolver import resolve_endpoint

        _, model, _ = resolve_endpoint("default")
        return {"ok": True, "teacher_model": model, "response": answer[:200]}

    @router.post("/api/admin/learning-ai/teach")
    async def teach_learning_ai(request: Request) -> dict[str, Any]:
        require_admin(request)
        body = await request.json()
        if not isinstance(body, dict):
            raise HTTPException(400, "JSON object required")
        transcript = str(body.get("transcript") or "").strip()
        if not transcript:
            raise HTTPException(400, "transcript is required")
        if len(transcript) > 30000:
            raise HTTPException(413, "transcript is too large")
        prompt = (
            "Analyze this trusted chat transcript for the local student model. "
            "Return ONLY JSON: {\"facts\":[{\"text\":\"...\",\"category\":\"fact\"}],"
            "\"skills\":[{\"title\":\"...\",\"problem\":\"...\",\"solution\":\"...\","
            "\"steps\":[\"...\"],\"tags\":[\"...\"],\"confidence\":0.0}]}. "
            "Keep only durable reusable facts and computer procedures; never include secrets. "
            "Maximum 5 facts and 2 skills.\n\nTRANSCRIPT:\n" + transcript
        )
        try:
            raw = await _default_model_reply([{"role": "user", "content": prompt}])
        except RuntimeError as exc:
            raise HTTPException(502, str(exc)) from exc
        from src.endpoint_resolver import resolve_endpoint

        _, teacher_model, _ = resolve_endpoint("default")
        start, end = raw.find("{"), raw.rfind("}")
        if start < 0 or end <= start:
            raise HTTPException(502, "Teacher returned no learning JSON")
        try:
            learned = json.loads(raw[start:end + 1])
        except json.JSONDecodeError as exc:
            raise HTTPException(502, "Teacher returned invalid learning JSON") from exc
        if not isinstance(learned, dict):
            raise HTTPException(502, "Teacher learning result must be an object")

        from services.memory.skills import SkillsManager
        from src.memory import MemoryManager
        memory_manager = getattr(request.app.state, "memory_manager", None) or MemoryManager(str(DATA_DIR))
        memory_vector = getattr(request.app.state, "memory_vector", None)
        skills_manager = getattr(request.app.state, "skills_manager", None) or SkillsManager(str(DATA_DIR))
        owner = "admin"
        stored_facts = 0
        entries = memory_manager.load_all_for_update()
        for fact in learned.get("facts", [])[:5]:
            if not isinstance(fact, dict) or not str(fact.get("text") or "").strip():
                continue
            text = str(fact["text"]).strip()[:500]
            if memory_manager.find_duplicates(text, entries):
                continue
            entry = memory_manager.add_entry(text, source="teacher", category=str(fact.get("category") or "fact"), owner=owner)
            entries.append(entry)
            if memory_vector and getattr(memory_vector, "healthy", False):
                memory_vector.add(entry["id"], entry["text"])
            stored_facts += 1
        if stored_facts:
            memory_manager.save(entries)
        stored_skills = 0
        for skill in learned.get("skills", [])[:2]:
            if not isinstance(skill, dict) or not str(skill.get("title") or "").strip():
                continue
            result = skills_manager.add_skill(
                title=str(skill.get("title") or "")[:120],
                problem=str(skill.get("problem") or "")[:500],
                solution=str(skill.get("solution") or "")[:800],
                steps=[str(step)[:300] for step in skill.get("steps", [])[:7]],
                tags=[str(tag)[:50] for tag in skill.get("tags", [])[:5]],
                source="teacher",
                teacher_model=str(teacher_model or ""),
                confidence=max(0.0, min(float(skill.get("confidence", 0.0)), 1.0)),
                owner=owner,
                status="verified",
            )
            if not result.get("_deduped"):
                stored_skills += 1
        return {
            "ok": True,
            "student_model": MODEL_ID,
            "teacher_model": teacher_model,
            "facts_stored": stored_facts,
            "skills_stored": stored_skills,
        }

    @router.post("/api/local-model/debate-prompt")
    async def debate_prompt(request: Request) -> dict[str, str]:
        body = await request.json()
        if not isinstance(body, dict):
            return JSONResponse({"error": {"message": "JSON object required"}}, status_code=400)
        try:
            prompt = build_debate_prompt(
                str(body.get("topic") or ""),
                int(body.get("rounds") or 5),
                str(body.get("language") or "Hinglish"),
            )
        except (TypeError, ValueError):
            return JSONResponse({"error": {"message": "rounds must be an integer"}}, status_code=400)
        return {"prompt": prompt}

    @router.post("/api/local-model/debate")
    async def run_debate(request: Request):
        body = await request.json()
        if not isinstance(body, dict) or not str(body.get("topic") or "").strip():
            return JSONResponse({"error": {"message": "topic is required"}}, status_code=400)
        try:
            rounds = max(1, min(int(body.get("rounds") or 5), 20))
            result = await _run_debate(
                str(body["topic"]).strip(),
                rounds,
                str(body.get("language") or "Hinglish"),
            )
        except (TypeError, ValueError):
            return JSONResponse({"error": {"message": "rounds must be an integer"}}, status_code=400)
        except RuntimeError as exc:
            return JSONResponse({"error": {"message": str(exc)}}, status_code=503)
        return result

    @router.get("/api/local-model/memory")
    async def local_model_memory(request: Request) -> dict[str, Any]:
        require_admin(request)
        conversation_count = 0
        debate_count = 0
        brain_count = 0
        brain_vector_healthy = False
        recent_topics: list[str] = []
        brain = getattr(request.app.state, "memory_manager", None)
        vector = getattr(request.app.state, "memory_vector", None)
        owner = _request_owner(request)
        if brain:
            brain_count = len(brain.load(owner=owner))
        brain_vector_healthy = bool(vector and getattr(vector, "healthy", False))
        try:
            if CONVERSATION_MEMORY_FILE.exists():
                conversation_count = sum(
                    1 for line in CONVERSATION_MEMORY_FILE.read_text(encoding="utf-8").splitlines() if line.strip()
                )
        except (FileNotFoundError, PermissionError, OSError):
            conversation_count = 0
        try:
            if DEBATE_MEMORY_FILE.exists():
                debate_count = sum(
                    1 for line in DEBATE_MEMORY_FILE.read_text(encoding="utf-8").splitlines() if line.strip()
                )
        except (FileNotFoundError, PermissionError, OSError):
            debate_count = 0

        try:
            for line in (DEBATE_MEMORY_FILE.read_text(encoding="utf-8").splitlines()[-10:]):
                if not line.strip():
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    continue
                topic = payload.get("topic")
                if isinstance(topic, str) and topic.strip():
                    recent_topics.append(topic.strip()[:120])
        except (FileNotFoundError, PermissionError, OSError):
            recent_topics = []

        return {
            "conversation_entries": conversation_count,
            "teacher_entries": len(_load_teacher_memory()),
            "debate_entries": debate_count,
            "brain_entries": brain_count,
            "brain_vector_healthy": brain_vector_healthy,
            "recent_topics": recent_topics,
            "model": MODEL_ID,
        }

    @router.get("/api/local-model/v1/models")
    async def list_local_models() -> dict[str, Any]:
        return {
            "object": "list",
            "data": _public_local_models(),
        }

    @router.post("/api/local-model/v1/chat/completions")
    async def local_chat_completions(request: Request):
        body = await request.json()
        messages = body.get("messages") if isinstance(body, dict) else []
        if not isinstance(messages, list):
            return JSONResponse({"error": {"message": "messages must be a list", "type": "invalid_request_error"}}, status_code=400)
        try:
            payload = await _response_payload(
                messages,
                bool(body.get("stream")),
                memory_manager=getattr(request.app.state, "memory_manager", None),
                memory_vector=getattr(request.app.state, "memory_vector", None),
                owner=_request_owner(request),
            )
        except RuntimeError as exc:
            return JSONResponse(
                {"error": {"message": str(exc), "type": "teacher_backend_error"}},
                status_code=502,
            )
        if body.get("stream"):
            return StreamingResponse(_stream_response(payload), media_type="text/event-stream")
        return payload

    return router
