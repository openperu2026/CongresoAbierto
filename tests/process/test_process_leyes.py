from datetime import datetime, UTC

from backend.database.raw_models import RawLey
from backend.process.schema import Ley
from backend.process.leyes import process_leyes


def _raw_ley(xml: str) -> RawLey:
    return RawLey(
        id="32558",
        timestamp=datetime.now(UTC),
        data=xml,
        processed=False,
        last_update=True,
        changed=True,
    )


def test_process_leyes_extracts_numley_title_and_bill_id():
    xml = """
    <root>
      <data>
        <ley>
          <numley>32558</numley>
          <tituloley>LEY DE PRUEBA</tituloley>
        </ley>
        <ignored></ignored>
        <recursos>
          <recursos>
            <tiporecursoleyitemmenu>2</tiporecursoleyitemmenu>
            <enlace>NOT_THIS_ONE</enlace>
          </recursos>
          <recursos>
            <tiporecursoleyitemmenu>6</tiporecursoleyitemmenu>
            <enlace>PL-12345</enlace>
          </recursos>
        </recursos>
      </data>
    </root>
    """.strip()

    out = process_leyes(_raw_ley(xml))

    assert isinstance(out, Ley)
    assert out.id == "32558"
    assert out.title == "LEY DE PRUEBA"
    assert out.bill_id == "PL-12345"


def test_process_leyes_returns_none_when_missing_required_fields():
    # Missing <tituloley> should cause AttributeError when .text_content() is called
    xml = """
    <root>
      <data>
        <ley>
          <numley>32558</numley>
        </ley>
        <ignored></ignored>
        <recursos>
          <recursos>
            <tiporecursoleyitemmenu>6</tiporecursoleyitemmenu>
            <enlace>PL-12345</enlace>
          </recursos>
        </recursos>
      </data>
    </root>
    """.strip()

    out = process_leyes(_raw_ley(xml))
    assert out is None


def test_process_leyes_returns_none_when_no_menu_item_6_present():
    xml = """
    <root>
      <data>
        <ley>
          <numley>32558</numley>
          <tituloley>LEY DE PRUEBA</tituloley>
        </ley>
        <ignored></ignored>
        <recursos>
          <recursos>
            <tiporecursoleyitemmenu>2</tiporecursoleyitemmenu>
            <enlace>NOPE</enlace>
          </recursos>
        </recursos>
      </data>
    </root>
    """.strip()

    out = process_leyes(_raw_ley(xml))
    assert out is None
