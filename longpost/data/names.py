"""Settlement and person names. Northern, plain, unremarkable."""

SETTLEMENT_STEMS = [
    "Kvit", "Nord", "Hest", "Sel", "Rein", "Skar", "Berg", "Vard", "Fisk",
    "Grim", "Hval", "Ravn", "Steins", "Myr", "Bjorn", "Vind", "Isle", "Torv",
    "Sag", "Furu", "Lang", "Elve", "Kald", "Sand", "Gard", "Ulv", "Havn",
    "Tind", "Fjell", "Sval", "Grav", "Aske", "Loft", "Rusk", "Vast",
]

SETTLEMENT_TAILS = [
    "vik", "hamn", "fjord", "nes", "berg", "dal", "sund", "oy", "botn",
    "strand", "eid", "gard", "voll", "haug", "os", "skar",
]

GIVEN_NAMES = [
    "Sigrid", "Ranveig", "Halvard", "Ingeborg", "Torfinn", "Aslaug", "Eirik",
    "Gudrun", "Steinar", "Solveig", "Brynjar", "Ragna", "Kjartan", "Astrid",
    "Vigdis", "Olav", "Hjalmar", "Turid", "Snorri", "Bergljot", "Arnulv",
    "Frida", "Leiv", "Marit", "Trygve", "Oddny", "Sverre", "Jorunn", "Haakon",
    "Alfhild", "Rolv", "Gyda", "Torgeir", "Silje", "Egil", "Runa", "Vemund",
    "Hedda", "Knut", "Signe",
]

PATRONYMS = [
    "Aslaksen", "Sund", "Berg", "Vollen", "Nes", "Hauge", "Skare", "Fjeld",
    "Sandvik", "Lind", "Roed", "Bakke", "Moen", "Straume", "Dahl", "Holt",
]


def settlement_names(gen, count):
    """`count` distinct settlement names drawn from a numpy Generator."""
    names, seen = [], set()
    while len(names) < count:
        name = (SETTLEMENT_STEMS[gen.integers(len(SETTLEMENT_STEMS))]
                + SETTLEMENT_TAILS[gen.integers(len(SETTLEMENT_TAILS))])
        if name in seen:
            continue
        seen.add(name)
        names.append(name)
    return names


def person_name(gen):
    return (f"{GIVEN_NAMES[gen.integers(len(GIVEN_NAMES))]} "
            f"{PATRONYMS[gen.integers(len(PATRONYMS))]}")
