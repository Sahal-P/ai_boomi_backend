"""Month names people write, in English, Hindi and Malayalam (also romanised), shared by the
question period reader (assistant/periods.py) and the date reader (ingestion/dates.py)."""

import unicodedata

ENGLISH: dict[str, int] = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "sept": 9,
    "october": 10,
    "november": 11,
    "december": 12,
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}
AMBIGUOUS = {"may", "march", "jan", "mar", "dec"}
NATIVE: dict[str, int] = {
    "जनवरी": 1,
    "फरवरी": 2,
    "फ़रवरी": 2,
    "मार्च": 3,
    "अप्रैल": 4,
    "मई": 5,
    "जून": 6,
    "जुलाई": 7,
    "अगस्त": 8,
    "सितंबर": 9,
    "सितम्बर": 9,
    "अक्टूबर": 10,
    "अक्तूबर": 10,
    "नवंबर": 11,
    "नवम्बर": 11,
    "दिसंबर": 12,
    "दिसम्बर": 12,
    "ജനുവരി": 1,
    "ഫെബ്രുവരി": 2,
    "മാർച്ച്": 3,
    "ഏപ്രിൽ": 4,
    "മേയ്": 5,
    "മെയ്": 5,
    "ജൂൺ": 6,
    "ജൂലൈ": 7,
    "ഓഗസ്റ്റ്": 8,
    "ആഗസ്റ്റ്": 8,
    "സെപ്റ്റംബർ": 9,
    "ഒക്ടോബർ": 10,
    "നവംബർ": 11,
    "ഡിസംബർ": 12,
}
# Romanised Hindi ("Hinglish") and Malayalam ("Manglish") spellings people type.
ROMANISED: dict[str, int] = {
    "janvari": 1,
    "janwari": 1,
    "januari": 1,
    "januvari": 1,
    "janavari": 1,
    "farvari": 2,
    "farwari": 2,
    "pharvari": 2,
    "februari": 2,
    "febravari": 2,
    "maarch": 3,
    "march": 3,
    "aprail": 4,
    "epril": 4,
    "april": 4,
    "mayi": 5,
    "joon": 6,
    "joonu": 6,
    "julai": 7,
    "joolai": 7,
    "agast": 8,
    "agasth": 8,
    "ogast": 8,
    "aagast": 8,
    "sitambar": 9,
    "sitamber": 9,
    "september": 9,
    "septembar": 9,
    "aktubar": 10,
    "aktoobar": 10,
    "october": 10,
    "oktobar": 10,
    "navambar": 11,
    "navamber": 11,
    "november": 11,
    "novembar": 11,
    "disambar": 12,
    "disamber": 12,
    "december": 12,
    "disembar": 12,
    "decembar": 12,
}


def normalized(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).casefold()
    return "".join(str(unicodedata.decimal(c)) if c.isdecimal() else c for c in text)


# Malayalam inflects a month's last letter ("ഓഗസ്റ്റിൽ", "സെപ്റ്റംബറിൽ"): match the stem too, with a
# final virama dropped or a chillu written as its consonant.
CHILLU = {"ൻ": "ന", "ർ": "റ", "ൽ": "ല", "ൾ": "ള", "ൺ": "ണ"}


def _stems(name: str) -> tuple[str, ...]:
    if name.endswith("്"):
        return (name, name[:-1])
    if name[-1:] in CHILLU:
        return (name, name[:-1] + CHILLU[name[-1]])
    return (name,)


NATIVE_NORMALIZED = {
    stem: month for name, month in NATIVE.items() for stem in _stems(normalized(name))
}
