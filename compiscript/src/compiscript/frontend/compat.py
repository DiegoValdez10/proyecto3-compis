from __future__ import annotations

import importlib
import sys
from typing import List

import antlr4.atn.ATNDeserializer as atn_module


def _decode_ints_encoded_as_16bit_words(data: str) -> List[int]:
    """Mirror ANTLR's char[] decoding for serialized ATNs.
    ANTLR 4.9.x encodes the integer stream as UTF-16 code units.  The Python
    runtime 4.13.x expects the already-decoded ``int`` sequence, so we emulate
    the Java helper ``decodeIntsEncodedAs16BitWords`` here.
    """

    decoded: List[int] = []
    idx = 0
    length = len(data)

    while idx < length:
        word = ord(data[idx])
        idx += 1

        if word & 0x8000 == 0:
            decoded.append(word)
            continue

        if idx >= length:
            raise ValueError("Truncated serialized ATN data")

        word2 = ord(data[idx])
        idx += 1

        if word == 0xFFFF and word2 == 0xFFFF:
            decoded.append(-1)
        else:
            decoded.append(((word & 0x7FFF) << 16) | (word2 & 0xFFFF))

    return decoded


def ensure_v3_atn_support() -> None:
    """Allow deserializing grammars generated with ANTLR 4.9.x.
    The repository ships parser artifacts generated with ANTLR 4.9.3, which
    encode the serialized ATN using version ``3``.  The Python runtime bundled
    in the project is 4.13.x and expects serialized version ``4`` by default.
    To keep backwards compatibility without regenerating every artifact during
    the exercises, we relax the version check before loading the grammar.
    """

    expected = getattr(atn_module, "SERIALIZED_VERSION", None)

    if expected == 4:

        # Prefer the regenerated ANTLR 4.13 artifacts when they are packaged
        # under ``generated/program/program`` while still keeping the original
        # 4.9.3 files available for reference.
        try:
            modern_pkg = importlib.import_module(
                "compiscript.frontend.generated.program.program"
            )
        except ImportError:
            modern_pkg = None

        if modern_pkg is not None:
            for module_name in (
                "CompiscriptParser",
                "CompiscriptLexer",
                "CompiscriptListener",
                "CompiscriptVisitor",
            ):
                try:
                    modern_module = importlib.import_module(
                        f"compiscript.frontend.generated.program.program.{module_name}"
                    )
                except ImportError:
                    continue
                sys.modules[
                    f"compiscript.frontend.generated.program.{module_name}"
                ] = modern_module

        original_deserialize = atn_module.ATNDeserializer.deserialize

        def _deserialize(self, data):
            if isinstance(data, str):
                data = _decode_ints_encoded_as_16bit_words(data)
            return original_deserialize(self, data)

        atn_module.ATNDeserializer.deserialize = _deserialize

        def _check_version(self):
            version = self.readInt()
            if version in (expected, 3):
                return
            raise Exception(
                "Could not deserialize ATN with version "
                + str(version)
                + " (expected 4 or backward-compatible 3)."
            )

        atn_module.ATNDeserializer.checkVersion = _check_version


# Apply the adjustment on import so clients only need to import this module.
ensure_v3_atn_support()