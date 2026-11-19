"""create_and_post_prompt must return the Telegram message_id, not the NULL one
read back at INSERT time (it made POST /v1/prompts fail PromptOut validation -> 400
even though the message had been delivered)."""
from unittest.mock import AsyncMock, patch

from tg_gateway.services.prompts import schemas, service


async def _fake_conn():
    yield object()


async def test_create_and_post_prompt_returns_telegram_message_id():
    insert_row = {"chat_id": "123", "message_id": None}

    with (
        patch.object(service, "get_conn", new=_fake_conn),
        patch(
            "tg_gateway.services.channels.models.get_channel",
            new=AsyncMock(return_value={"telegram_chat_id": 123, "bot_token": "t"}),
        ),
        patch.object(
            service.models, "create_prompt", new=AsyncMock(return_value=("#7", insert_row))
        ),
        patch(
            "tg_gateway.core.telegram_bot.post_prompt_to_chat",
            new=AsyncMock(return_value=4242),
        ),
    ):
        prompt_id, row = await service.create_and_post_prompt(
            chat_id=None, channel_id="c", text="hi", media_path=None, media_url=None,
            options=["A"], allow_text=False, callback_url=None, correlation_id=None,
            ttl_sec=60,
        )

    assert prompt_id == "#7"
    assert row["message_id"] == 4242
    # and the response model the endpoint builds now validates
    out = schemas.PromptOut(prompt_id=prompt_id, chat_id=row["chat_id"], message_id=row["message_id"])
    assert out.message_id == 4242
