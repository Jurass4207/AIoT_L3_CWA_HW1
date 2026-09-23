"""
api/index.py
預設 API 入口點：重導向/引用 api.weather.handler
提供 GET /api 與 GET /api/index 氣象觀測資料
"""

from .weather import handler

__all__ = ["handler"]
