# app/services/github_utils.py 

from typing import List, Optional

def parse_labels(labels_json: Optional[List[str]]) -> List[str]:
    """Преобразует JSON labels в список строк"""
    if not labels_json:
        return []
    return labels_json

def has_label(labels_json: Optional[List[str]], label_name: str) -> bool:
    """Проверяет, есть ли у задачи определённая метка"""
    if not labels_json:
        return False
    return label_name in labels_json