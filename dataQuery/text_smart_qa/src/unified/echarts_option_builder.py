from __future__ import annotations

from typing import List


def build_echarts_option(chart: dict) -> dict:
    """根据智能问数输出的 chart 结构生成 ECharts option。"""
    chart_type = str(chart.get("type") or "bar").strip() or "bar"
    if chart_type == "pie":
        return _build_pie_option(chart)
    if chart_type == "line":
        return _build_line_option(chart)
    if chart_type == "bar_line":
        return _build_bar_line_option(chart)
    if chart_type == "bar_horizontal":
        return _build_horizontal_bar_option(chart)
    return _build_bar_option(chart)


def _build_line_option(chart: dict) -> dict:
    """生成折线图 option，带渐变面积背景。"""
    labels = [str(item) for item in chart.get("labels", [])]
    series_list = _normalize_series(chart)
    palette = _chart_palette()

    series = []
    for index, item in enumerate(series_list):
        color = palette[index % len(palette)]
        series.append(
            {
                "name": item["name"],
                "type": "line",
                "smooth": True,
                "showSymbol": True,
                "symbol": "circle",
                "symbolSize": 9,
                "data": item["values"],
                "lineStyle": {
                    "width": 3,
                    "color": color,
                    "shadowBlur": 10,
                    "shadowColor": _to_rgba(color, 0.18),
                },
                "itemStyle": {
                    "color": color,
                    "borderColor": "#ffffff",
                    "borderWidth": 2,
                },
                "areaStyle": {
                    "color": {
                        "type": "linear",
                        "x": 0,
                        "y": 0,
                        "x2": 0,
                        "y2": 1,
                        "colorStops": [
                            {"offset": 0, "color": _to_rgba(color, 0.35)},
                            {"offset": 1, "color": _to_rgba(color, 0.04)},
                        ],
                    }
                },
                "emphasis": {
                    "focus": "series",
                    "scale": True,
                },
            }
        )

    return _build_cartesian_option(
        title=str(chart.get("title") or "图表"),
        labels=labels,
        series=series,
        legend_names=[item["name"] for item in series_list],
    )


def _build_bar_option(chart: dict) -> dict:
    """生成 2D 柱状图 option。"""
    labels = [str(item) for item in chart.get("labels", [])]
    series_list = _normalize_series(chart)
    palette = _chart_palette()
    series: List[dict] = []

    for index, item in enumerate(series_list):
        color = palette[index % len(palette)]
        series.append(
            {
                "name": item["name"],
                "type": "bar",
                "data": item["values"],
                "barWidth": 24,
                "barMaxWidth": 32,
                "barGap": "30%",
                "itemStyle": {
                    "borderRadius": [0, 0, 0, 0],
                    "shadowBlur": 10,
                    "shadowOffsetX": 0,
                    "shadowOffsetY": 5,
                    "shadowColor": _to_rgba(color, 0.12),
                    "color": {
                        "type": "linear",
                        "x": 0,
                        "y": 0,
                        "x2": 0,
                        "y2": 1,
                        "colorStops": [
                            {"offset": 0, "color": _lighten_color(color, 0.14)},
                            {"offset": 0.35, "color": _lighten_color(color, 0.05)},
                            {"offset": 1, "color": _darken_color(color, 0.08)},
                        ],
                    },
                },
                "label": {
                    "show": True,
                    "position": "top",
                    "color": "#334155",
                    "fontSize": 11,
                    "fontWeight": "bold",
                    "distance": 8,
                },
                "emphasis": {
                    "focus": "series",
                    "itemStyle": {
                        "shadowBlur": 14,
                        "shadowColor": _to_rgba(color, 0.18),
                    },
                },
            }
        )

    option = _build_cartesian_option(
        title=str(chart.get("title") or "图表"),
        labels=labels,
        series=series,
        legend_names=[item["name"] for item in series_list],
    )
    option["xAxis"]["axisLabel"]["interval"] = 0
    return option


def _build_bar_line_option(chart: dict) -> dict:
    """生成柱线混合图 option。"""
    labels = [str(item) for item in chart.get("labels", [])]
    series_list = _normalize_series(chart)
    palette = _chart_palette()
    series: List[dict] = []

    for index, item in enumerate(series_list):
        color = palette[index % len(palette)]
        if index == 0:
            series.append(
                {
                    "name": item["name"],
                    "type": "bar",
                    "data": item["values"],
                    "barWidth": 24,
                    "itemStyle": {
                        "borderRadius": [0, 0, 0, 0],
                        "shadowBlur": 10,
                        "shadowOffsetX": 0,
                        "shadowOffsetY": 5,
                        "shadowColor": _to_rgba(color, 0.12),
                        "color": {
                            "type": "linear",
                            "x": 0,
                            "y": 0,
                            "x2": 0,
                            "y2": 1,
                            "colorStops": [
                                {"offset": 0, "color": _lighten_color(color, 0.14)},
                                {"offset": 0.35, "color": _lighten_color(color, 0.05)},
                                {"offset": 1, "color": _darken_color(color, 0.08)},
                            ],
                        },
                    },
                    "label": {
                        "show": True,
                        "position": "top",
                        "color": "#334155",
                        "fontSize": 11,
                        "fontWeight": "bold",
                        "distance": 8,
                    },
                    "emphasis": {
                        "focus": "series",
                        "itemStyle": {
                            "shadowBlur": 14,
                            "shadowColor": _to_rgba(color, 0.18),
                        },
                    },
                }
            )
        else:
            series.append(
                {
                    "name": item["name"],
                    "type": "line",
                    "smooth": True,
                    "showSymbol": True,
                    "symbol": "circle",
                    "symbolSize": 9,
                    "yAxisIndex": 0,
                    "data": item["values"],
                    "lineStyle": {"width": 3, "color": color},
                    "itemStyle": {
                        "color": color,
                        "borderColor": "#ffffff",
                        "borderWidth": 2,
                    },
                    "areaStyle": {
                        "color": {
                            "type": "linear",
                            "x": 0,
                            "y": 0,
                            "x2": 0,
                            "y2": 1,
                            "colorStops": [
                                {"offset": 0, "color": _to_rgba(color, 0.28)},
                                {"offset": 1, "color": _to_rgba(color, 0.03)},
                            ],
                        }
                    },
                }
            )

    option = _build_cartesian_option(
        title=str(chart.get("title") or "图表"),
        labels=labels,
        series=series,
        legend_names=[item["name"] for item in series_list],
    )
    return option


def _build_horizontal_bar_option(chart: dict) -> dict:
    """生成横向柱状图 option。"""
    labels = [str(item) for item in chart.get("labels", [])]
    series_list = _normalize_series(chart)
    palette = _chart_palette()
    series = []

    for index, item in enumerate(series_list):
        color = palette[index % len(palette)]
        series.append(
            {
                "name": item["name"],
                "type": "bar",
                "data": item["values"],
                "barWidth": 22,
                "itemStyle": {
                    "borderRadius": [0, 10, 10, 0],
                    "shadowBlur": 10,
                    "shadowColor": _to_rgba(color, 0.20),
                    "color": {
                        "type": "linear",
                        "x": 0,
                        "y": 0,
                        "x2": 1,
                        "y2": 0,
                        "colorStops": [
                            {"offset": 0, "color": _lighten_color(color, 0.16)},
                            {"offset": 1, "color": _darken_color(color, 0.10)},
                        ],
                    },
                },
                "label": {
                    "show": True,
                    "position": "right",
                    "color": "#334155",
                    "fontSize": 11,
                },
            }
        )

    option = _build_cartesian_option(
        title=str(chart.get("title") or "图表"),
        labels=labels,
        series=series,
        legend_names=[item["name"] for item in series_list],
        horizontal=True,
    )
    option["grid"]["left"] = 100
    return option


def _build_pie_option(chart: dict) -> dict:
    """生成 2D 饼图 option。"""
    labels = [str(item) for item in chart.get("labels", [])]
    values = [float(item or 0) for item in chart.get("values", [])]
    palette = _chart_palette()

    pie_data = []
    for index, (label, value) in enumerate(zip(labels, values)):
        color = palette[index % len(palette)]
        pie_data.append(
            {
                "name": label,
                "value": value,
                "itemStyle": {
                    "color": color,
                    "shadowBlur": 18,
                    "shadowColor": _to_rgba(color, 0.28),
                },
            }
        )

    return {
        "backgroundColor": "#ffffff",
        "title": {
            "text": str(chart.get("title") or "图表"),
            "left": "center",
            "top": 14,
            "textStyle": {
                "color": "#1f2937",
                "fontSize": 18,
                "fontWeight": "bold",
            },
        },
        "color": palette,
        "tooltip": {
            "trigger": "item",
            "backgroundColor": "rgba(15, 23, 42, 0.92)",
            "borderWidth": 0,
            "textStyle": {"color": "#ffffff"},
            "formatter": "{b}<br/>{c} ({d}%)",
        },
        "legend": {
            "bottom": 8,
            "left": "center",
            "icon": "circle",
            "textStyle": {"color": "#475569", "fontSize": 11},
        },
        "series": [
            {
                "name": str(chart.get("title") or "图表"),
                "type": "pie",
                "radius": ["0%", "62%"],
                "center": ["50%", "50%"],
                "selectedMode": "single",
                "selectedOffset": 6,
                "avoidLabelOverlap": True,
                "label": {
                    "show": True,
                    "formatter": "{b}\n{d}%",
                    "color": "#334155",
                    "fontSize": 11,
                },
                "labelLine": {
                    "length": 16,
                    "length2": 14,
                    "lineStyle": {"color": "#94a3b8"},
                },
                "itemStyle": {
                    "borderColor": "#ffffff",
                    "borderWidth": 2,
                },
                "emphasis": {
                    "scale": True,
                    "scaleSize": 6,
                },
                "data": pie_data,
            },
        ],
    }


def _build_cartesian_option(
    title: str,
    labels: List[str],
    series: List[dict],
    legend_names: List[str],
    horizontal: bool = False,
) -> dict:
    """生成柱状图、折线图、混合图共用的基础 option。"""
    option = {
        "backgroundColor": "#ffffff",
        "color": _chart_palette(),
        "title": {
            "text": title,
            "left": "center",
            "top": 14,
            "textStyle": {
                "color": "#1f2937",
                "fontSize": 18,
                "fontWeight": "bold",
            },
        },
        "tooltip": {
            "trigger": "axis" if not horizontal else "item",
            "axisPointer": {
                "type": "shadow" if any(item.get("type") == "bar" for item in series) else "line",
                "shadowStyle": {"color": "rgba(148, 163, 184, 0.12)"},
            },
            "backgroundColor": "rgba(15, 23, 42, 0.92)",
            "borderWidth": 0,
            "textStyle": {"color": "#ffffff"},
        },
        "legend": {
            "top": 48,
            "icon": "roundRect",
            "itemWidth": 14,
            "itemHeight": 10,
            "textStyle": {"color": "#475569", "fontSize": 11},
            "data": legend_names,
        },
        "grid": {
            "left": 56,
            "right": 28,
            "top": 92,
            "bottom": 56,
            "containLabel": True,
        },
        "xAxis": {
            "type": "value" if horizontal else "category",
            "data": None if horizontal else labels,
            "axisTick": {"show": False},
            "axisLine": {"lineStyle": {"color": "#cbd5e1"}},
            "axisLabel": {"color": "#475569", "fontSize": 11, "margin": 10},
        },
        "yAxis": {
            "type": "category" if horizontal else "value",
            "data": labels if horizontal else None,
            "splitLine": {"lineStyle": {"type": "dashed", "color": "#dbe4f0"}},
            "axisLine": {"show": False},
            "axisTick": {"show": False},
            "axisLabel": {"color": "#475569", "fontSize": 11, "margin": 12},
        },
        "series": series,
    }

    if len(labels) > 12 and not horizontal:
        option["dataZoom"] = [
            {"type": "inside", "start": 0, "end": 60},
            {"type": "slider", "height": 14, "bottom": 14, "start": 0, "end": 60},
        ]
    return option


def _normalize_series(chart: dict) -> List[dict]:
    """把原始图表中的 series 统一整理成 name + values 结构。"""
    raw_series = chart.get("series") or []
    output = []
    for index, item in enumerate(raw_series):
        output.append(
            {
                "name": str(item.get("name") or f"系列{index + 1}"),
                "values": [float(value or 0) for value in item.get("values", [])],
            }
        )

    if output:
        return output

    values = [float(value or 0) for value in chart.get("values", [])]
    if values:
        return [{"name": str(chart.get("title") or "数值"), "values": values}]
    return []


def _chart_palette() -> List[str]:
    """统一的图表配色。"""
    return [
        "#2F6FED",
        "#12B886",
        "#F59F00",
        "#E64980",
        "#7C5CFF",
        "#0EA5E9",
        "#82C91E",
        "#F76707",
    ]


def _to_rgba(hex_color: str, alpha: float) -> str:
    """把十六进制颜色转换成 rgba 字符串。"""
    clean = hex_color.lstrip("#")
    if len(clean) != 6:
        return f"rgba(47, 111, 237, {alpha})"
    red = int(clean[0:2], 16)
    green = int(clean[2:4], 16)
    blue = int(clean[4:6], 16)
    return f"rgba({red}, {green}, {blue}, {alpha})"


def _lighten_color(hex_color: str, ratio: float) -> str:
    """把颜色按比例调亮。"""
    return _mix_color(hex_color, "#ffffff", ratio)


def _darken_color(hex_color: str, ratio: float) -> str:
    """把颜色按比例调暗。"""
    return _mix_color(hex_color, "#0f172a", ratio)


def _mix_color(from_color: str, to_color: str, ratio: float) -> str:
    """按比例混合两种颜色。"""
    ratio = max(0.0, min(1.0, ratio))
    from_rgb = _hex_to_rgb(from_color)
    to_rgb = _hex_to_rgb(to_color)
    mixed = []
    for start, end in zip(from_rgb, to_rgb):
        value = round(start + (end - start) * ratio)
        mixed.append(max(0, min(255, value)))
    return "#{:02X}{:02X}{:02X}".format(*mixed)


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    """把十六进制颜色转换成 RGB 元组。"""
    clean = hex_color.lstrip("#")
    if len(clean) != 6:
        return 47, 111, 237
    return int(clean[0:2], 16), int(clean[2:4], 16), int(clean[4:6], 16)
