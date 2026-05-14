"""wickworks — stateless OHLC primitives service.

Bars in, indicators + SMC objects out. No scoring, no signals, no opinion.
"""

from importlib.metadata import PackageNotFoundError, version as _pkg_version

try:
    __version__ = _pkg_version("wickworks")
except PackageNotFoundError:
    # Editable / source checkout where the dist-info is missing. Source of
    # truth stays pyproject.toml; this is just a friendly fallback for
    # running straight out of a clone without `pip install`.
    __version__ = "0.0.0+unknown"
