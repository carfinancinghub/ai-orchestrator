from core.providers import load_provider
from core.providers.echo import EchoProvider

def test_load_provider_echo():
    p = load_provider("echo")
    assert isinstance(p, EchoProvider)
    assert p.generate("Hello").startswith("ECHO: ")
