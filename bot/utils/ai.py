import os
import asyncio
import logging

logger = logging.getLogger(__name__)

HC_AI_API_KEY = os.getenv("HC_AI_API_KEY")

_processing: set[int] = set()


def is_available() -> bool:
    return bool(HC_AI_API_KEY)


def _sanitize_channel_name(title: str) -> str:
    sanitized = title.lower().strip()
    sanitized = sanitized.replace(" ", "-")
    sanitized = "".join(c for c in sanitized if c.isalnum() or c in "-_")
    sanitized = sanitized.strip("-")
    return sanitized[:100] or "ticket"


async def suggest_ticket_title(conversation: str) -> str | None:
    if not HC_AI_API_KEY:
        return None

    def _call():
        from openrouter import OpenRouter

        client = OpenRouter(
            api_key=HC_AI_API_KEY,
            server_url="https://ai.hackclub.com/proxy/v1",
        )
        response = client.chat.send(
            model="qwen/qwen3-32b",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You analyze support ticket conversations. Based on the conversation, "
                        "suggest a short, descriptive title (max 50 chars) for the ticket that "
                        "summarizes the main issue or topic. Use only letters, numbers, spaces, "
                        "and hyphens — no special characters. "
                        "If there is NOT enough information to determine the topic, respond with "
                        'exactly "NOT_ENOUGH_INFO". Otherwise respond with ONLY the title, nothing else.'
                    ),
                },
                {"role": "user", "content": f"Conversation:\n\n{conversation}"},
            ],
            stream=False,
            temperature=0.3,
            max_tokens=80,
        )
        return response.choices[0].message.content.strip()

    try:
        raw = await asyncio.to_thread(_call)
    except ImportError:
        logger.warning("openrouter package not installed. Run: pip install openrouter")
        return None
    except Exception as e:
        logger.warning(f"AI title suggestion failed: {e}")
        return None

    if not raw or raw.upper() == "NOT_ENOUGH_INFO":
        return None

    title = raw.strip('"').strip("'").strip()
    return _sanitize_channel_name(title)


def is_processing(ticket_id: int) -> bool:
    return ticket_id in _processing


def mark_processing(ticket_id: int):
    _processing.add(ticket_id)


def unmark_processing(ticket_id: int):
    _processing.discard(ticket_id)
