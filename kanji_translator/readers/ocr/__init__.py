"""The maintained literal Japanese OCR engine."""
def local_engine(config):
    if config.get('backend','ndl')!='ndl':raise ValueError('Tesseract is retired; use NDLOCR')
    from .ndlocr_lite import NDLOCR
    return NDLOCR(config)
