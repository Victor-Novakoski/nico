import os

import psycopg
import pytest

from nico.migrate import migrate


@pytest.fixture
def db_url() -> str:
    """Banco de teste migrado e limpo (schema recriado); pula sem NICO_TEST_DATABASE_URL."""
    url = os.environ.get("NICO_TEST_DATABASE_URL")
    if not url:
        pytest.skip("NICO_TEST_DATABASE_URL não definida")
    with psycopg.connect(url, autocommit=True) as setup:
        setup.execute("drop schema public cascade")
        setup.execute("create schema public")
    migrate(url)
    return url
