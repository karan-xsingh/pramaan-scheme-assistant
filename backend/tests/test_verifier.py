from app.verifier import numbers, sentence_spans, should_reject, verify

SOURCES = [
    {
        "n": 1,
        "excerpt": "Under PM-KISAN, eligible farmer families receive income support of Rs. 6,000 per year "
        "in three equal instalments of Rs. 2,000, paid directly into the bank account.",
    },
    {
        "n": 2,
        "excerpt": "Documents required: Aadhaar number, land ownership records and a bank account number.",
    },
]


def statuses(answer):
    v = verify(answer, SOURCES)
    return v, [c["status"] for c in v["claims"]]


def test_sentence_split_keeps_abbreviations_and_decimals():
    text = "PM-KISAN pays Rs. 6,000 per year [1]. Houses get 1.30 lakh [2]."
    spans = sentence_spans(text)
    assert len(spans) == 2
    assert text[spans[0][0] : spans[0][1]].endswith("[1].")


def test_numbers_ignore_citations_and_commas():
    assert numbers("Rs. 6,000 per year [1]") == {6000.0}
    assert numbers("1.20 lakh and 1.2 lakh") == {1.2}


def test_supported_answer_is_high():
    v, st = statuses("PM-KISAN pays Rs. 6,000 per year to farmer families [1].")
    assert st == ["supported"]
    assert v["level"] == "high"


def test_invented_number_is_unsupported():
    v, st = statuses("PM-KISAN pays Rs. 12,000 per year [1].")
    assert st == ["unsupported"]
    assert v["level"] == "low"


def test_number_from_other_source_is_weak():
    _, st = statuses("The Aadhaar number is needed and Rs. 6,000 is paid [2].")
    assert st == ["weak"]


def test_missing_citation_target_is_unsupported():
    _, st = statuses("Farmers get support [7].")
    assert st == ["unsupported"]


def test_invented_words_downgrade_to_weak():
    _, st = statuses("Farmers also receive a free tractor [1].")
    assert st == ["weak"]


def test_reminder_sentence_is_not_counted():
    v, st = statuses("Please confirm on the official website.")
    assert st == ["unchecked"]
    assert v["total"] == 0 and v["level"] == "unchecked"


def test_uncited_number_not_in_sources_is_unsupported():
    _, st = statuses("The scheme pays Rs. 9,999 every month.")
    assert st == ["unsupported"]


def test_hindi_sentence_against_english_source_checks_numbers_only():
    _, ok = statuses("पीएम किसान में साल में 6,000 रुपये मिलते हैं [1]।")
    _, bad = statuses("पीएम किसान में साल में 9,000 रुपये मिलते हैं [1]।")
    assert ok == ["supported"]
    assert bad == ["unsupported"]


def test_should_reject_when_half_unsupported():
    v, _ = statuses("PM-KISAN pays Rs. 12,000 [1]. It also pays Rs. 6,000 per year to farmer families [1].")
    assert should_reject(v)
    good, _ = statuses("PM-KISAN pays Rs. 6,000 per year to farmer families [1].")
    assert not should_reject(good)
