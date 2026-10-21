import json

from langchain_kapso import parse_inbound_messages, verify_signature

from .conftest import SECRET, received_payload, sign


def test_valid_signature():
    body = b'{"a": 1}'
    assert verify_signature(body, sign(body), SECRET)


def test_signature_of_reserialized_body_fails():
    body = b'{"a":  1}'
    reserialized = json.dumps(json.loads(body)).encode()
    assert not verify_signature(reserialized, sign(body), SECRET)


def test_missing_or_wrong_signature():
    assert not verify_signature(b"{}", None, SECRET)
    assert not verify_signature(b"{}", "abc", SECRET)


def test_parse_single_message():
    [message] = parse_inbound_messages(received_payload("Hola"), "whatsapp.message.received")
    assert message.text == "Hola"
    assert message.conversation_id == "conv_1"
    assert message.from_phone == "51987654321"
    assert message.contact_name == "Ana"


def test_parse_batch_uses_type_from_body():
    payload = {
        "type": "whatsapp.message.received",
        "batch": True,
        "data": [received_payload("uno", "wamid.1"), received_payload("dos", "wamid.2")],
    }
    assert [m.text for m in parse_inbound_messages(payload)] == ["uno", "dos"]


def test_other_events_are_ignored():
    assert parse_inbound_messages(received_payload(), "whatsapp.message.delivered") == []


def test_button_reply_uses_title():
    payload = received_payload()
    payload["message"] = {
        "id": "wamid.9",
        "type": "interactive",
        "interactive": {"type": "button_reply", "button_reply": {"id": "yes", "title": "Sí"}},
        "kapso": {"direction": "inbound"},
    }
    [message] = parse_inbound_messages(payload, "whatsapp.message.received")
    assert message.text == "Sí"
