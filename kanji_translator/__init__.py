"""Canonical public parser API. All operations preserve source-owned originals."""
from .document_parser import parse,read_retained
from .candidate_lookup import candidates
__all__=['parse','candidates','read_retained']
