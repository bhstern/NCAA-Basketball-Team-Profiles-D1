"""
Frozen-history write guard — EVERY pipeline write must go through this module.

Rules (checked on the fully resolved path, so ".." and symlinks can't sneak past):

    1. Outside CBB_ROOT                     -> allowed (scratch / temp dirs)
    2. Inside a sandbox (_scrape_test,
       _rebuild)                            -> allowed, any season (validation runs)
    3. Inside a never-write location
       (frozen career files)                -> refused, any season
    4. Anywhere else inside CBB_ROOT        -> allowed ONLY if:
         - season == CURRENT_SEASON, and
         - the path contains no frozen year token (catches "2016-2026 Master ...",
           "2025trank_...", etc. even if the caller passes the wrong season), and
         - the path names the current season (e.g. "2027trank_...", "by_year/2027/"),
           unless it is on the explicit unseasoned allowlist (e.g. a year manifest)

Anything else raises FrozenHistoryError BEFORE a byte is written.
Writes are atomic (temp file + os.replace), so a crash never leaves a half-written file.
"""

import os
import re
import tempfile
from pathlib import Path

from . import config

# Left edge must not be alphanumeric so hash fragments like "..._bc2027.json" don't count;
# right edge may be a letter ("2027trank_...").
YEAR_TOKEN = re.compile(r"(?<![A-Za-z0-9])(20\d{2})(?!\d)")


class FrozenHistoryError(PermissionError):
    pass


class WriteGuard:

    def __init__(self, protected_root, sandbox_roots, frozen_seasons, current_season,
                 unseasoned_allowlist=(), never_write_roots=()):
        self.protected_root = Path(os.path.realpath(protected_root))
        self.sandbox_roots = tuple(Path(os.path.realpath(s)) for s in sandbox_roots)
        self.never_write_roots = tuple(Path(os.path.realpath(s)) for s in never_write_roots)
        self.frozen_seasons = frozenset(frozen_seasons)
        self.current_season = current_season
        self.unseasoned_allowlist = frozenset(
            Path(os.path.realpath(p)) for p in unseasoned_allowlist
        )

    @staticmethod
    def _is_within(path, root):
        return path == root or root in path.parents

    def check(self, path, season):
        """Raise FrozenHistoryError if writing `path` for `season` is not allowed."""
        resolved = Path(os.path.realpath(path))

        if not self._is_within(resolved, self.protected_root):
            return resolved

        if any(self._is_within(resolved, s) for s in self.sandbox_roots):
            return resolved

        if any(self._is_within(resolved, n) for n in self.never_write_roots):
            raise FrozenHistoryError(
                f"Refusing write inside never-write location (frozen history): {resolved}"
            )
        if season is None:
            raise FrozenHistoryError(
                f"Refusing write without a season inside protected tree: {resolved}"
            )
        if season in self.frozen_seasons:
            raise FrozenHistoryError(
                f"Refusing write for FROZEN season {season}: {resolved}"
            )
        if season != self.current_season:
            raise FrozenHistoryError(
                f"Refusing write for season {season} (current season is "
                f"{self.current_season}): {resolved}"
            )

        rel = resolved.relative_to(self.protected_root)
        tokens = {int(y) for y in YEAR_TOKEN.findall(str(rel))}
        frozen_tokens = sorted(tokens & self.frozen_seasons)
        if frozen_tokens:
            raise FrozenHistoryError(
                f"Refusing write: path names frozen season(s) {frozen_tokens}: {resolved}"
            )
        if self.current_season not in tokens and resolved not in self.unseasoned_allowlist:
            raise FrozenHistoryError(
                f"Refusing write: path does not name season {self.current_season} "
                f"and is not allowlisted: {resolved}"
            )

        return resolved

    # -----------------------------------------------------------------------
    # Guarded writers
    # -----------------------------------------------------------------------

    def _atomic_write(self, path, season, write_fn):
        target = self.check(path, season)
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=target.parent, prefix=f".{target.name}.", suffix=".tmp")
        os.close(fd)
        try:
            write_fn(tmp)
            os.replace(tmp, target)
        finally:
            if os.path.exists(tmp):
                os.remove(tmp)
        return target

    def write_bytes(self, path, data, season):
        def _w(tmp):
            with open(tmp, "wb") as f:
                f.write(data)
        return self._atomic_write(path, season, _w)

    def write_text(self, path, text, season, encoding="utf-8"):
        return self.write_bytes(path, text.encode(encoding), season)

    def to_csv(self, df, path, season, **kwargs):
        return self._atomic_write(path, season, lambda tmp: df.to_csv(tmp, **kwargs))


DEFAULT_GUARD = WriteGuard(
    protected_root=config.CBB_ROOT,
    sandbox_roots=config.SANDBOX_ROOTS,
    frozen_seasons=config.FROZEN_SEASONS,
    current_season=config.CURRENT_SEASON,
    never_write_roots=config.NEVER_WRITE_ROOTS,
)

check = DEFAULT_GUARD.check
write_bytes = DEFAULT_GUARD.write_bytes
write_text = DEFAULT_GUARD.write_text
to_csv = DEFAULT_GUARD.to_csv
