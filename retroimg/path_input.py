"""Terminal path entry, isolated from menus and image conversion."""
from __future__ import annotations

import os
import sys
from typing import Callable

from prompt_toolkit import prompt
from prompt_toolkit.completion import Completion, PathCompleter


class DirectoryPathCompleter(PathCompleter):
    """Complete literal paths and include the separator when entering a folder."""

    def __init__(self):
        super().__init__(expanduser=True)

    def get_completions(self, document, complete_event):
        for completion in super().get_completions(document, complete_event):
            candidate = document.text_before_cursor + completion.text
            if os.path.isdir(os.path.expanduser(candidate)):
                # Honour forward-slash paths on Windows as well as native ones.
                separator = '/' if '/' in candidate and '\\' not in candidate else os.sep
                yield Completion(completion.text + separator,
                                 start_position=completion.start_position,
                                 display=completion.display)
            else:
                yield completion


def read_path(message: str, *, fallback: Callable[[str], str]) -> str:
    """Use Tab completion on terminals; retain ordinary input for pipes/tests."""
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        return fallback(message)
    return prompt(message, completer=DirectoryPathCompleter(),
                  complete_while_typing=False)
