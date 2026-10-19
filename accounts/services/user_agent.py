import re
from typing import Dict


def parse_user_agent(user_agent_str: str | None) -> Dict[str, str]:
    """
    Safely parses browser, operating system, and device category from User-Agent string.
    Never fails or throws exceptions on unusual strings.
    """
    if not user_agent_str:
        return {
            'browser': 'Unknown Browser',
            'os': 'Unknown OS',
            'device_type': 'Desktop / Web Client',
            'raw': 'Not Available'
        }

    ua = str(user_agent_str).strip()

    # Inferred Device Category
    if re.search(r'iPad|tablet|PlayBook|Silk', ua, re.IGNORECASE):
        device_type = 'Tablet'
    elif re.search(r'Mobile|iP(hone|od)|Android.*Mobile|webOS|BlackBerry|IEMobile|Opera Mini', ua, re.IGNORECASE):
        device_type = 'Mobile'
    else:
        device_type = 'Desktop'

    # Inferred Operating System
    if 'Windows NT 10.0' in ua:
        os_name = 'Windows 10/11'
    elif 'Windows NT 6.3' in ua:
        os_name = 'Windows 8.1'
    elif 'Windows NT 6.1' in ua:
        os_name = 'Windows 7'
    elif 'Windows' in ua:
        os_name = 'Windows'
    elif 'iPhone' in ua:
        os_name = 'iOS (iPhone)'
    elif 'iPad' in ua:
        os_name = 'iPadOS'
    elif 'Macintosh' in ua or 'Mac OS X' in ua:
        os_name = 'macOS'
    elif 'Android' in ua:
        os_name = 'Android'
    elif 'Linux' in ua:
        os_name = 'Linux'
    elif 'CrOS' in ua:
        os_name = 'ChromeOS'
    else:
        os_name = 'Unknown Operating System'

    # Inferred Browser
    if 'Edg/' in ua or 'Edge/' in ua:
        browser_name = 'Microsoft Edge'
    elif 'OPR/' in ua or 'Opera/' in ua:
        browser_name = 'Opera'
    elif 'Chrome/' in ua and 'Safari/' in ua:
        browser_name = 'Google Chrome'
    elif 'Firefox/' in ua:
        browser_name = 'Mozilla Firefox'
    elif 'Safari/' in ua and 'Version/' in ua:
        browser_name = 'Apple Safari'
    elif 'MSIE ' in ua or 'Trident/' in ua:
        browser_name = 'Internet Explorer'
    else:
        browser_name = 'Web Browser'

    return {
        'browser': browser_name,
        'os': os_name,
        'device_type': device_type,
        'raw': ua[:150]
    }
