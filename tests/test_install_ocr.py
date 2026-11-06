import pytest
from kanji_translator import install_ocr
from kanji_translator.readers.ocr import ndlocr_lite

def test_readiness_exposes_missing_engine(monkeypatch):
    def fail(config):raise RuntimeError('missing native reader')
    monkeypatch.setattr(ndlocr_lite,'runtime',fail)
    result=install_ocr.readiness()
    assert result['state']=='unavailable' and result['reason']=='missing native reader'

def test_retired_backend_fails_with_migration():
    with pytest.raises(ValueError,match='retired; use NDLOCR'):install_ocr.readiness('tesseract')
