"""Evaluators for agent version v2.

Currently identical to v1. Cloned rather than shared because an evaluator is
injected into three agents at once, so editing the v1 module in place would
silently change frozen v1 behaviour. See docs/VERSIONING.md.
"""
VERSION = "v2"

# Imported here so `getattr(evaluation.v2, "<game>_eval")` works - the
# tournament looks evaluators up by name from the version package.
from evaluation.v2 import ataxx_eval, isolation_eval, uttt_eval  # noqa: F401
