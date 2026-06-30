from typing import Any


def replace_corpus_in_list(
    corpora: list[dict[str, Any]],
    updated_corpus: dict[str, Any],
) -> list[dict[str, Any]]:
    updated_id = str(updated_corpus.get("id"))
    return [
        {**corpus, **updated_corpus}
        if str(corpus.get("id")) == updated_id
        else corpus
        for corpus in corpora
    ]
