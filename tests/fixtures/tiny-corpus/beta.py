"""Beta side of the fixture corpus: the callee alpha depends on."""


def normalize(name):
    return name.strip().lower()


def shout(name):
    return normalize(name).upper()
