import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2] / "frontend"))

from state_utils import replace_corpus_in_list


def test_replace_corpus_in_list_updates_renamed_corpus_without_refresh() -> None:
    corpora = [
        {"id": 1, "name": "Old Name", "document_count": 2},
        {"id": 2, "name": "Other Corpus", "document_count": 1},
    ]
    updated = {"id": 1, "name": "New Name"}

    result = replace_corpus_in_list(corpora, updated)

    assert result[0]["name"] == "New Name"
    assert result[0]["document_count"] == 2
    assert result[1]["name"] == "Other Corpus"
