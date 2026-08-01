"""检测器模块：差异比对。"""

from .diff import InventoryActivity, analyze_activity, classify_activity, detect_changes

__all__ = ["detect_changes", "analyze_activity", "classify_activity", "InventoryActivity"]
