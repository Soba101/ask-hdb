"""Display names for places stored in capitals: capitalised words, small words in lower case, known acronyms kept."""

from string import capwords

SMALL = {"of", "and", "the", "for"}
ACRONYMS = {"CHIJ", "ACS", "SJI", "MRT", "LRT", "BTO", "NUS", "NTU", "SIM"}


def pretty_name(value):
    words = capwords(str(value)).split()
    out = []
    for i, word in enumerate(words):
        if word.upper() in ACRONYMS:
            out.append(word.upper())
        elif i and word.lower() in SMALL:
            out.append(word.lower())
        else:
            out.append(word)
    return " ".join(out)
