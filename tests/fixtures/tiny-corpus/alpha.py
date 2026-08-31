"""Alpha side of the fixture corpus: calls into beta so the graph gets a real edge."""

from beta import normalize


def greet(name):
    return f"hello, {normalize(name)}"


def greet_all(names):
    return [greet(n) for n in names]
