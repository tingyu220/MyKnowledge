# -*- coding: utf-8 -*-
"""
ISBN 验证与标准化工具
支持 ISBN-10、ISBN-13；兼容全角数字、GTIN-14（前导 0）、嵌入在长串中的 978/979。
"""
import re
import unicodedata


def normalize_isbn(isbn):
    """
    标准化 ISBN：NFKC（全角数字等）、移除分隔符，仅保留 0-9 与 X。
    返回标准化字符串，无法识别则返回 None。
    """
    if isbn is None:
        return None
    if isinstance(isbn, int):
        isbn = str(isbn)
    if isinstance(isbn, float):
        if isbn != isbn:  # NaN
            return None
        isbn = str(int(isbn)) if isbn == int(isbn) else str(isbn)
    if not isinstance(isbn, str):
        return None

    s0 = unicodedata.normalize('NFKC', isbn.strip())
    s = re.sub(r'[^0-9Xx]', '', s0).upper()

    if not s:
        return None

    # GTIN-14：图书类常见前导 0 + 13 位 EAN/ISBN
    if len(s) == 14 and s.isdigit() and s[0] == '0':
        s = s[1:]

    # 长串中提取 ISBN-13（扫码可能带前缀后缀）
    if len(s) > 13:
        m = re.search(r'(?:978|979)\d{10}', s)
        if m:
            s = m.group(0)
        else:
            return None

    if len(s) == 10 and (s[:9].isdigit() and (s[9].isdigit() or s[9] == 'X')):
        return s
    if len(s) == 13 and s.isdigit():
        return s
    return None


def validate_isbn(isbn):
    """
    验证 ISBN 格式，支持 ISBN-10 与 ISBN-13（含校验位）。
    """
    isbn_clean = normalize_isbn(isbn)
    if not isbn_clean:
        return False
    if len(isbn_clean) == 10:
        return validate_isbn10(isbn_clean)
    if len(isbn_clean) == 13:
        return validate_isbn13(isbn_clean)
    return False


def validate_isbn10(isbn):
    """验证 ISBN-10"""
    if len(isbn) != 10:
        return False

    total = 0
    for i in range(9):
        if not isbn[i].isdigit():
            return False
        total += int(isbn[i]) * (10 - i)

    check_digit = isbn[9]
    if check_digit == 'X':
        check_value = 10
    elif check_digit.isdigit():
        check_value = int(check_digit)
    else:
        return False

    return (total + check_value) % 11 == 0


def validate_isbn13(isbn):
    """验证 ISBN-13"""
    if len(isbn) != 13:
        return False

    if not isbn.isdigit():
        return False

    total = 0
    for i in range(12):
        multiplier = 1 if i % 2 == 0 else 3
        total += int(isbn[i]) * multiplier

    check_digit = (10 - (total % 10)) % 10

    return check_digit == int(isbn[12])
