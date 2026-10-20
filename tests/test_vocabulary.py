from conftest import reader
from pytest_bdd import given, parsers, scenarios, then, when

from bookplate import outbound

scenarios("vocabulary.feature")


@given(parsers.parse('Wiktionary defines "{word}" as "{definition}"'))
def wiktionary(monkeypatch, word, definition):
    entry = {
        "word": word,
        "phonetic": None,
        "senses": [{"partOfSpeech": "noun", "definition": definition, "example": None}],
    }
    monkeypatch.setattr(outbound, "define", lambda w: entry if w.lower() == word else None)


@when(parsers.parse('they look up "{word}"'))
def look_up(ctx, word):
    ctx["response"] = reader(ctx).get("/api/define", params={"word": word})


@then(parsers.parse('the lookup offers "{definition}"'))
def offers(ctx, definition):
    assert ctx["response"].json()["entry"]["senses"][0]["definition"] == definition


@then("the lookup has no entry")
def no_entry(ctx):
    assert ctx["response"].json() == {"entry": None}


@given(parsers.parse('they saved the word "{word}" meaning "{definition}" from "{title}"'))
@when(parsers.parse('they save the word "{word}" meaning "{definition}" from "{title}"'))
def save_word(ctx, word, definition, title):
    reader(ctx).post("/vocabulary", data={"word": word, "definition": definition, "book_id": ctx["ids"].get(title, "")})


@given(parsers.parse('they saved the word "{word}" meaning "{definition}" from no book'))
def save_loose_word(ctx, word, definition):
    save_word(ctx, word, definition, "")


@when(parsers.parse('they delete the word "{word}"'))
def delete_word(ctx, word):
    entry = next(w for w in reader(ctx).get("/api/vocabulary").json()["words"] if w["word"] == word)
    reader(ctx).post(f"/vocabulary/{entry['id']}/delete")


@when(parsers.parse('they save a word with the return address "{back}"'))
def save_with_back(ctx, back):
    ctx["response"] = reader(ctx).post("/vocabulary", data={"word": "w", "definition": "d", "back": back})
