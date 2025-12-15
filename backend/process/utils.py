import re
from backend import PARTY_ALIASES


def extract_text(text: str, initial: str = None, final: str = None) -> str:
    """
    Extracts the text between an specified initial and final texts. The initial
    or the final text could be optional, but not both

    Args:
        - text: original text
        - initial: initial part of the text to start
        - final: final part of the text to stop the extraction
    """
    assert initial or final, "Must specify either initial or final text"

    if initial and final:
        pattern = re.compile(f"{re.escape(initial)}(.*?){re.escape(final)}", re.DOTALL)
    elif initial and not final:
        pattern = re.compile(f"({re.escape(initial)})(.*)", re.DOTALL)
    else:
        pattern = re.compile(f"(.*?){re.escape(final)}", re.DOTALL)
    result = re.search(pattern, text)

    if not final:
        return result.group(2)
    else:
        return result.group(1)


def normalize_party_name(name: str) -> str:
    if name in PARTY_ALIASES.keys():
        canonical_name = PARTY_ALIASES[name]
        return canonical_name
    return name
