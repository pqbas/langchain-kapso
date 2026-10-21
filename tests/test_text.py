import random

import httpx
import pytest

from langchain_kapso import KapsoClient, KapsoToolkit, split_message
from langchain_kapso.text import WHATSAPP_TEXT_LIMIT

from .conftest import PHONE_NUMBER_ID, received_payload, webhook_request
from .test_bridge import make_bridge


def words(text: str) -> list[str]:
    return text.split()


def test_short_text_is_one_chunk():
    assert split_message("Hola, ¿en qué te ayudo?") == ["Hola, ¿en qué te ayudo?"]


def test_empty_text_gives_no_chunks():
    assert split_message("   ") == []


def test_cuts_between_paragraphs_first():
    first, second = "a" * 60, "b" * 60
    assert split_message(f"{first}\n\n{second}", limit=100) == [first, second]


def test_cuts_between_sentences_before_words():
    text = "Tu pedido A100 fue enviado ayer. Llega en tres días hábiles a Trujillo."
    assert split_message(text, limit=50) == ["Tu pedido A100 fue enviado ayer.", "Llega en tres días hábiles a Trujillo."]


def test_cuts_inside_a_word_only_when_there_is_no_space():
    assert split_message("x" * 250, limit=100) == ["x" * 100, "x" * 100, "x" * 50]


def test_default_limit_is_whatsapp_limit():
    chunks = split_message("palabra " * 2000)
    assert len(chunks) > 1 and all(len(c) <= WHATSAPP_TEXT_LIMIT for c in chunks)


def test_invalid_limit():
    with pytest.raises(ValueError):
        split_message("hola", limit=0)


@pytest.mark.parametrize("seed", range(300))
def test_random_texts_respect_the_limit_and_keep_every_word(seed):
    rng = random.Random(seed)
    pieces = []
    for _ in range(rng.randint(1, 80)):
        word = "".join(rng.choice("abcdeñáé") for _ in range(rng.randint(1, 30)))
        pieces.append(word + rng.choice([" ", " ", " ", ". ", "\n", "\n\n", "! "]))
    text = "".join(pieces)
    limit = rng.randint(5, 120)

    chunks = split_message(text, limit=limit)

    assert all(0 < len(c) <= limit for c in chunks)
    # Joining the chunks gives back the same words; only words longer than the limit are cut
    assert "".join(words("".join(chunks))) == "".join(words(text))


async def test_bridge_sends_a_long_reply_in_order(recorder):
    bridge = make_bridge(recorder)
    bridge.max_message_length = 20
    long_text = "Primera parte del texto. Segunda parte del texto. Tercera."
    await bridge.handle(*webhook_request(received_payload(long_text)))

    sent = [b["text"]["body"] for b in recorder.bodies() if b.get("type") == "text"]
    # The echo graph answers "<text> (1)"
    assert " ".join(sent) == f"{long_text} (1)"
    assert len(sent) > 1 and all(len(s) <= 20 for s in sent)


def test_send_text_tool_splits_long_messages(recorder):
    client = KapsoClient(api_key="k", phone_number_id=PHONE_NUMBER_ID, http_client=httpx.Client(transport=httpx.MockTransport(recorder)))
    tool = {t.name: t for t in KapsoToolkit(client=client).get_tools()}["kapso_send_text"]
    result = tool.invoke({"to": "51987654321", "body": "x " * 3000})
    assert result.startswith("Message sent in 2 parts")
    assert len(recorder.bodies()) == 2
