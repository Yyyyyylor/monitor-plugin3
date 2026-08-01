"""Steam ID 参数验证器。"""

import re


def validate_steam_id(steam_id: str) -> tuple[bool, str]:
    """验证 Steam ID 格式。
    
    Args:
        steam_id: 待验证的 Steam ID 字符串
        
    Returns:
        (是否有效，错误信息/空字符串)
    """
    if not steam_id or not steam_id.strip():
        return False, "Steam ID 不能为空"
    
    # 17 位数字验证
    pattern = r'^\d{17}$'
    if not re.match(pattern, steam_id):
        return False, "Steam ID 必须是 17 位数字"
    
    return True, ""


def validate_frequency(frequency: str) -> tuple[bool, str]:
    """验证监控频率。
    
    Args:
        frequency: 频率值 (high | medium | low)
        
    Returns:
        (是否有效，错误信息/空字符串)
    """
    valid_frequencies = ["high", "medium", "low"]
    if frequency not in valid_frequencies:
        return False, f"无效的频率 '{frequency}'，请输入 high、medium 或 low"
    
    return True, ""
