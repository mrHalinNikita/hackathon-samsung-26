import re

def clean_ocr_text(text: str) -> str:

    if not text:
        return ""
    
    text = re.sub(r'(\d)\s+(?=\d)', r'\1', text)
    
    text = re.sub(r'([А-ЯЁ])\s+(?=[А-ЯЁ])', r'\1', text)
    
    text = re.sub(r'(?<=\d)O(?=\d)', '0', text)
    text = re.sub(r'(?<=\d)I(?=\d)', '1', text)
    text = re.sub(r'(?<=\d)l(?=\d)', '1', text)
    
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text