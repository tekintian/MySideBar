from dataclasses import dataclass


SCOPE_NAME = "name"
SCOPE_PATH = "path"

MODE_REGEX = "regex"
MODE_SEQUENCE = "sequence"


@dataclass(frozen=True)
class RenameOptions:
    mode: str = MODE_REGEX
    pattern: str = ""
    replacement: str = ""
    prefix: str = ""
    start: int = 1
    digits: int = 3
    suffix: str = ""
    scope: str = SCOPE_NAME
    recursive: bool = False
    include_dirs: bool = False

    def is_sequence(self):
        return self.mode == MODE_SEQUENCE

    def normalized(self):
        digits = self.digits
        if digits < 1:
            digits = 1
        elif digits > 10:
            digits = 10
        start = self.start
        if start < 0:
            start = 0
        scope = self.scope if self.scope in (SCOPE_NAME, SCOPE_PATH) else SCOPE_NAME
        mode = self.mode if self.mode in (MODE_REGEX, MODE_SEQUENCE) else MODE_REGEX
        return RenameOptions(
            mode=mode,
            pattern=self.pattern,
            replacement=self.replacement,
            prefix=self.prefix,
            start=start,
            digits=digits,
            suffix=self.suffix,
            scope=scope,
            recursive=bool(self.recursive),
            include_dirs=bool(self.include_dirs),
        )