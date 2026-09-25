"""Layer 1 sources, one module per central bank (see banks/common.py for the
interface). Adding a bank = a new module here plus one line in SOURCES."""
from . import boc, boe, ecb, fed

SOURCES = {"fed": fed, "ecb": ecb, "boe": boe, "boc": boc}
