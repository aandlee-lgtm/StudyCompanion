"""Citation parsing and resolution corpus (audit legal-01/02/21).

Each row: text -> exact list of (kind, name as found, status) against a small fixed bank."""
from __future__ import annotations

from datetime import date

import pytest

from app.services.citations import Bank, currency, parse_citations, redact, resolve, unique

TODAY = date(2026, 10, 13)

BANK = Bank([
    {"id": 1, "title": "Crimes Act 1900 (NSW)", "item_type": "legislation", "status": "in_force", "last_verified_date": date(2026, 10, 1)},
    {"id": 2, "title": "Bail Act 2013 (NSW)", "item_type": "legislation", "status": "in_force", "aliases": ["Bail Act"]},
    {"id": 3, "title": "Young Offenders Act 1997 (NSW)", "item_type": "legislation", "status": "in_force"},
    {"id": 4, "title": "Crimes (Sentencing Procedure) Act 1999 (NSW)", "item_type": "legislation", "status": "in_force"},
    {"id": 5, "title": "Children (Criminal Proceedings) Act 1987 (NSW)", "item_type": "legislation"},
    {"id": 6, "title": "RP v The Queen [2016] HCA 53", "item_type": "case", "last_verified_date": date(2026, 9, 1)},
    {"id": 7, "title": "Universal Declaration of Human Rights (1948)", "item_type": "treaty"},
    {"id": 8, "title": "International Covenant on Civil and Political Rights (1966)", "item_type": "treaty"},
    {"id": 9, "title": "Australian Human Rights Commission Act 1986 (Cth)", "item_type": "legislation"},
    {"id": 10, "title": "Racial Discrimination Act 1975 (Cth)", "item_type": "legislation"},
    {"id": 11, "title": "Mabo v Queensland (No 2) (1992) 175 CLR 1", "item_type": "case"},
    {"id": 12, "title": "Charter of Human Rights and Responsibilities Act 2006 (Vic)", "item_type": "legislation"},
    {"id": 13, "title": "Law Enforcement (Powers and Responsibilities) Act 2002 (NSW)", "item_type": "legislation", "aliases": ["LEPRA"]},
    {"id": 14, "title": "Bail Act 1978 (NSW)", "item_type": "legislation", "status": "repealed", "superseded_by": "Bail Act 2013 (NSW)"},
    {"id": 15, "title": "Pathways to Justice – Inquiry into the Incarceration Rate of Aboriginal and Torres Strait Islander Peoples (ALRC Report 133)",
     "item_type": "report", "aliases": ["Pathways to Justice"]},
    {"id": 16, "title": "Convention on the Rights of the Child (1989)", "item_type": "treaty"},
    {"id": 17, "title": "Evidence Act 1995 (NSW)", "item_type": "legislation", "last_verified_date": date(2025, 1, 1)},
])

V, U, N, O, S, R = "verified", "unverified", "not_in_bank", "outdated", "no_source", "recheck_due"

CORPUS = [
    ("Crimes Act 1900 (NSW) s 61", [("legislation", "Crimes Act 1900 (NSW)", V)]),
    ("R v Smith", [("case", "R v Smith", N)]),
    ("Smith v The Queen [2016] HCA 1", [("case", "Smith v The Queen [2016] HCA 1", N)]),
    ("the Bail Act", [("legislation", "Bail Act", U)]),
    ("Under the Bail Act 2013 (NSW), bail is decided on unacceptable risk.", [("legislation", "Bail Act 2013 (NSW)", U)]),
    ("In R v Dunn the court held", [("case", "R v Dunn", N)]),
    ("The case of Mabo v Queensland (No 2) recognised native title.", [("case", "Mabo v Queensland (No 2)", U)]),
    ("Mabo (No 2)", [("case", "Mabo (No 2)", U)]),
    ("Mabo v Queensland (No 3)", [("case", "Mabo v Queensland (No 3)", N)]),
    ("Mabo v Queensland (No 2) (1992) 175 CLR 1", [("case", "Mabo v Queensland (No 2) (1992) 175 CLR 1", U)]),
    ("RP v The Queen [2016] HCA 53 is leading.", [("case", "RP v The Queen [2016] HCA 53", V)]),
    ("RP v R", [("case", "RP v R", V)]),
    ("RP v The Queen [2017] HCA 53", [("case", "RP v The Queen [2017] HCA 53", N)]),
    ("Bugmy v The Queen (2013) 249 CLR 571", [("case", "Bugmy v The Queen (2013) 249 CLR 571", N)]),
    ("The Crimes Legislation Amendment (Coercive Control) Act 2022 (NSW) criminalised coercive control.",
     [("legislation", "Crimes Legislation Amendment (Coercive Control) Act 2022 (NSW)", N)]),
    ("the Young Offenders Act", [("legislation", "Young Offenders Act", U)]),
    ("YOA 1997 (NSW)", [("legislation", "YOA 1997 (NSW)", U)]),
    ("the CSPA (NSW)", [("legislation", "CSPA (NSW)", U)]),
    ("LEPRA 2002 (NSW)", [("legislation", "LEPRA 2002 (NSW)", U)]),
    ("Law Enforcement (Powers and Responsibilities) Act 2002 (NSW)", [("legislation", "Law Enforcement (Powers and Responsibilities) Act 2002 (NSW)", U)]),
    ("In 2023 the NSW Parliament passed the Fake Reform Act 2024 (NSW).", [("legislation", "Fake Reform Act 2024 (NSW)", N)]),
    ("Following the Royal Commission into Institutional Responses to Child Sexual Abuse (2017),",
     [("inquiry", "Royal Commission into Institutional Responses to Child Sexual Abuse", N)]),
    ("The ALRC report Pathways to Justice (2017) found", [("report", "Pathways to Justice", U)]),
    ("Article 9 of the ICCPR", [("treaty", "ICCPR", U)]),
    ("Convention on the Rights of the Child (1989)", [("treaty", "Convention on the Rights of the Child", U)]),
    ("Momcilovic v R", [("case", "Momcilovic v R", N)]),
    ("DPP (NSW) v Smith", [("case", "DPP (NSW) v Smith", N)]),
    ("the Racial Discrimination Act 1975 (Cth)", [("legislation", "Racial Discrimination Act 1975 (Cth)", U)]),
    ("Overall, the law is effective. However The Act 2013 is good.", []),
    ("Under the Crimes Act, murder carries life imprisonment.", [("legislation", "Crimes Act", V)]),
    ("Act 1900", []),
    ("Section 22 of the Evidence Act 1995 (NSW)", [("legislation", "Evidence Act 1995 (NSW)", R)]),
    ("According to the BOCSAR 2024 report, remand rates rose by 37%.",
     [("statistic", "According to the BOCSAR 2024 report, remand rates rose by 37%.", S), ("report", "BOCSAR 2024 report", N)]),
    ("In Zhang v Wong, the court", [("case", "Zhang v Wong", N)]),
    ("R v Abdul-Rahman (2021)", [("case", "R v Abdul-Rahman (2021)", N)]),
    ("Re Kerry (No 2)", [("case", "Re Kerry (No 2)", N)]),
    ("Charter of Human Rights and Responsibilities Act 2006 (Vic)", [("legislation", "Charter of Human Rights and Responsibilities Act 2006 (Vic)", U)]),
    ("Responsibilities Act 2006 shows", [("legislation", "Responsibilities Act 2006", N)]),
    ("Human Rights Commission Act 1986", [("legislation", "Human Rights Commission Act 1986", N)]),
    ("the Human Rights Act 2004 (ACT)", [("legislation", "Human Rights Act 2004 (ACT)", N)]),
    ("the Crimes (Sentencing Procedure) Act 1999", [("legislation", "Crimes (Sentencing Procedure) Act 1999", U)]),
    ("The Universal Declaration of Human Rights", [("treaty", "Universal Declaration of Human Rights", U)]),
    ("Lange v Australian Broadcasting Corporation (1997)", [("case", "Lange v Australian Broadcasting Corporation (1997)", N)]),
    ("Australian Capital Television Pty Ltd v Commonwealth (1992)", [("case", "Australian Capital Television Pty Ltd v Commonwealth (1992)", N)]),
    ("Al-Kateb v Godwin (2004)", [("case", "Al-Kateb v Godwin (2004)", N)]),
    ("Wik Peoples v Queensland (1996)", [("case", "Wik Peoples v Queensland (1996)", N)]),
    ("NZYQ v Minister for Immigration [2023] HCA 37", [("case", "NZYQ v Minister for Immigration [2023] HCA 37", N)]),
    ("In Mabo v Queensland (No 2) and later the Native Title Act 1993 (Cth)",
     [("case", "Mabo v Queensland (No 2)", U), ("legislation", "Native Title Act 1993 (Cth)", N)]),
    ("Under the Bail Act 1978 (NSW) there is a presumption in favour of bail.", [("legislation", "Bail Act 1978 (NSW)", O)]),
    ("International Covenant on Economic, Social and Cultural Rights, which Australia ratified",
     [("treaty", "International Covenant on Economic, Social and Cultural Rights", N)]),
    ("Bail laws are highly effective overall. Under the Bail Act 1978 (NSW) and Smith v Jones (2024), the court protects rights.",
     [("legislation", "Bail Act 1978 (NSW)", O), ("case", "Smith v Jones (2024)", N)]),
    ("About 40 per cent of prisoners are on remand.", [("statistic", "About 40 per cent of prisoners are on remand.", S)]),
    ("The impact of this fact in practice is that people interact and react.", []),
]


@pytest.mark.parametrize("text,expected", CORPUS, ids=[c[0][:40] for c in CORPUS])
def test_corpus(text, expected):
    got = [(r.citation.kind, r.citation.name, r.status) for r in unique(resolve(text, BANK, TODAY))]
    assert got == expected


def test_resolution_is_per_item_not_substring():
    # a fragment of a real title must not pass as the real item
    assert [r.status for r in resolve("Rights Commission Act 1986 (Cth)", BANK, TODAY)] == ["not_in_bank"]


def test_repealed_act_names_its_replacement():
    r = resolve("Under the Bail Act 1978 (NSW), bail was presumed.", BANK, TODAY)[0]
    assert r.status == "outdated" and "Bail Act 2013 (NSW)" in r.note


def test_older_year_of_bank_act_is_possibly_outdated_without_a_repealed_item():
    bank = Bank([{"title": "Bail Act 2013 (NSW)", "item_type": "legislation", "status": "in_force"}])
    r = resolve("Under the Bail Act 1978 (NSW) bail was presumed.", bank, TODAY)[0]
    assert r.status == "not_in_bank" and r.possibly_outdated and r.note.startswith("Possible issue — verify:")


def test_statistic_with_bank_source_in_sentence_is_sourced():
    rs = resolve("The ALRC report Pathways to Justice (2017) found that 27 per cent of prisoners were Aboriginal.", BANK, TODAY)
    assert [(r.citation.kind, r.status) for r in rs] == [("statistic", "sourced"), ("report", "unverified")]


def test_pinpoints_and_fields():
    c = parse_citations("Section 22 of the Evidence Act 1995 (NSW)")[0]
    assert (c.name, c.year, c.jurisdiction, c.pinpoint) == ("Evidence Act 1995 (NSW)", 1995, "nsw", "s 22")
    c = parse_citations("Mabo v Queensland (No 2) (1992) 175 CLR 1")[0]
    assert (c.number, c.year, c.report_cite) == (2, 1992, "(1992) 175 CLR 1")
    c = parse_citations("Article 9 of the ICCPR")[0]
    assert c.pinpoint == "Article 9"


def test_currency_is_oldest_of_cited_items():
    text = "Crimes Act 1900 (NSW), RP v The Queen [2016] HCA 53 and the Bail Act 2013 (NSW)."
    cur = currency(resolve(text, BANK, TODAY), TODAY)
    assert cur["checked"] == "2026-09-01" and cur["cited"] == 3 and cur["verified_count"] == 2
    assert cur["unverified"] == ["Bail Act 2013 (NSW)"]


def test_recheck_interval_from_settings():
    rs = resolve("Crimes Act 1900 (NSW)", BANK, TODAY, {"legal_recheck_days_legislation": 7})
    assert rs[0].status == "recheck_due"


def test_redact_removes_only_authorities_not_in_bank():
    text = "Under the Bail Act 2013 (NSW) and R v Fabricated (2024), bail is refused."
    out, removed = redact(text, resolve(text, BANK, TODAY))
    assert removed == ["R v Fabricated (2024)"]
    assert "Bail Act 2013 (NSW)" in out and "[authority removed: not in your evidence bank]" in out


# ------------------------------------------------------------------ recovery of slightly-off spans ---

@pytest.mark.parametrize("text, title", [
    ("As the High Court in RP v The Queen [2016] HCA 53 held, doli incapax must be rebutted.", "RP v The Queen [2016] HCA 53"),
    ("The Convention on the Rights of the Child (1989), Article 40, requires a separate system.", "Convention on the Rights of the Child (1989)"),
    ("Victoria's Charter of Human Rights and Responsibilities Act 2006 (Vic)'s dialogue model is weak.",
     "Charter of Human Rights and Responsibilities Act 2006 (Vic)"),
])
def test_recovered_citations_resolve_to_the_bank(text, title):
    rs = [r for r in unique(resolve(text, BANK, TODAY)) if r.citation.kind != "statistic"]
    assert rs and all(r.status != N for r in rs), [(r.citation.name, r.status) for r in rs]
    assert any(r.item and r.item.title == title for r in rs)


def test_recovery_never_turns_a_protocol_into_its_convention_or_admits_a_wrong_year():
    rs = unique(resolve("The Optional Protocol to the Convention on the Rights of the Child applies.", BANK, TODAY))
    assert not any(r.item and r.item.title.startswith("Convention on the Rights of the Child") for r in rs)
    rs = unique(resolve("The Bail Act 1999 (NSW) applies.", BANK, TODAY))
    assert all(r.status == N for r in rs)
