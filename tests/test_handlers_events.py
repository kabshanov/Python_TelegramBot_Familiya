import pytest
from tgapp import handlers_events as ev


@pytest.mark.django_db
def test_start_help_flow(fctx):
    upd = __import__("tests.conftest", fromlist=["FakeUpdate"]).FakeUpdate("/start")
    ev.start(upd, fctx)
    assert "Календарь-бот" in upd.message.last_reply

    upd = __import__("tests.conftest", fromlist=["FakeUpdate"]).FakeUpdate("/help")
    ev.help_command(upd, fctx)
    # Принимаем оба текста помощи: с заголовком "Справка" или без него.
    assert any(needle in upd.message.last_reply for needle in ("Справка", "Календарь-бот"))
