from __future__ import annotations
import json
import os
import threading
from datetime import datetime
import requests
from fastapi import APIRouter, HTTPException, Query
from topaz_us.analysis.query import load_analysis_results
from topaz_us.analysis.daily import analyze_stocks
from topaz_us.reports.sender import build_score_ranking_blocks
from backend.routers.common import PROJECT_ROOT, patch_results

router = APIRouter()

NASDAQ100_STOCK_LIST = os.path.join(PROJECT_ROOT, "config", "nasdaq100_stocks.json")
STATUS_FILE = os.path.join(PROJECT_ROOT, "data/raw/analysis_status.json")
RESULT_FILE = os.path.join(PROJECT_ROOT, "data/raw/latest_analysis_results.json")

_lock = threading.Lock()
_status = {"status": "idle", "progress": 0, "message": ""}


def _save_status(status: str, progress: int, message: str):
    global _status
    with _lock:
        _status = {"status": status, "progress": progress, "message": message}
    os.makedirs(os.path.dirname(STATUS_FILE), exist_ok=True)
    with open(STATUS_FILE, "w") as f:
        json.dump(_status, f)


@router.get("/daily")
def daily_analysis():
    data = load_analysis_results()
    if data is None:
        return {"error": "暂无分析结果，请先触发分析"}
    regime = data.get("market_regime", "sideways")
    qqq_above_ma200 = data.get("qqq_above_ma200", True)
    results = data.get("results", data.get("all_results", []))
    data["results"] = patch_results(results, regime, qqq_above_ma200)
    return data


@router.get("/status")
def analysis_status():
    with _lock:
        return dict(_status)


@router.get("/report")
def analysis_report():
    data = load_analysis_results()
    if data is None:
        return {"error": "暂无分析结果", "text": ""}

    results = data.get("results", data.get("all_results", []))
    if not results:
        return {"error": "暂无分析结果", "text": ""}

    regime = data.get("market_regime", "sideways")
    qqq_above_ma200 = data.get("qqq_above_ma200", True)
    results = patch_results(results, regime, qqq_above_ma200)

    confidence = data.get("model_confidence", 1.0)
    adv_ratio = data.get("advance_ratio", 0.5)
    position = data.get("recommended_position", 0.5)
    date = data.get("date", datetime.now().strftime("%Y-%m-%d %H:%M"))

    sorted_by_score = sorted(results, key=lambda x: x.get("composite_score", 0), reverse=True)

    regime_names = {"bull": "Bull trend", "bear": "Bear risk", "sideways": "Sideways", "pullback": "Pullback"}
    regime_name = regime_names.get(regime, regime)

    lines = []
    lines.append("Topaz US Moon Accumulation + Liquidity Exit Daily Report")
    lines.append(f"⏱ {date}")
    lines.append("")
    lines.append(f"Market: {regime_name} | Benchmark: QQQ | Coverage breadth: {adv_ratio:.1%}")
    lines.append(f"Suggested gross exposure: {position:.0%}")
    if not qqq_above_ma200:
        lines.append("QQQ is below MA200; active buy signals are capped to watch/observe.")
    lines.append("")

    buy_list = [r for r in sorted_by_score if r.get("advice") == "建议买入"]
    avoid_list = [r for r in sorted_by_score if r.get("advice") == "建议回避"]

    if buy_list:
        lines.append("Buy Candidates")
        for i, s in enumerate(buy_list[:10], 1):
            adv = s.get("advice", "")
            score = s.get("composite_score", 0)
            rsn = " | ".join(s.get("reasons", []))[:80]
            pos = s.get("position_pct", 0)
            lines.append(f"  #{i} {s['symbol']} {s['name']} ({s.get('sector', s.get('industry', ''))})")
            lines.append(f"     Score: {score:.1f} | Position: {pos:.0%} | {adv}")
            if s.get("entry_price") and s.get("stop_loss"):
                lines.append(f"     Entry: {s['entry_price']:.2f} | Initial stop: {s['stop_loss']:.2f}")
            if rsn:
                lines.append(f"     Reasons: {rsn}")
        lines.append("")

    if avoid_list:
        lines.append("Avoid List")
        for i, s in enumerate(avoid_list[:8], 1):
            score = s.get("composite_score", 0)
            adv = s.get("advice", "")
            lines.append(f"  #{i} {s['symbol']} {s['name']} Score: {score:.1f} | {adv}")
        lines.append("")

    buy_count = len(buy_list)
    watch_count = len([r for r in sorted_by_score if r.get("advice") == "可以关注"])
    observe_count = len([r for r in sorted_by_score if r.get("advice") == "建议观望"])
    avoid_count = len(avoid_list)
    lines.append(f"Distribution: Buy {buy_count} / Watch {watch_count} / Observe {observe_count} / Avoid {avoid_count}")
    lines.append("")
    lines.append("For research only. Not investment advice.")

    return {"text": "\n".join(lines), "error": ""}


SLACK_CONFIGS_FILE = os.path.join(PROJECT_ROOT, "data/raw/slack_configs.json")


def _send_slack_report(token: str, channel: str, results: list, regime: str, confidence: float, adv_ratio: float) -> str:
    if not token:
        return "Token 为空"
    blocks = build_score_ranking_blocks(results, regime, confidence, adv_ratio)
    payload = {
        "channel": channel,
        "blocks": blocks,
        "text": f"Topaz-Next 评分排名 - {datetime.now().strftime('%Y-%m-%d')}",
    }
    try:
        r = requests.post(
            "https://slack.com/api/chat.postMessage",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json=payload,
            timeout=30,
        )
        resp = r.json()
        if resp.get("ok"):
            return ""
        return f"Slack API 错误: {resp.get('error', 'unknown')}"
    except Exception:
        return "Slack 请求异常（网络或 API 错误）"


@router.post("/send-slack")
def send_to_slack(config: str = Query("", description="配置名称，空=发送给所有")):
    data = load_analysis_results()
    if data is None:
        raise HTTPException(status_code=400, detail="暂无分析结果")

    results = data.get("results", data.get("all_results", []))
    if not results:
        raise HTTPException(status_code=400, detail="暂无分析结果")

    regime = data.get("market_regime", "sideways")
    results = patch_results(results, regime, data.get("qqq_above_ma200", True))

    confidence = data.get("model_confidence", 0.5)
    adv_ratio = data.get("advance_ratio", 0.5)

    configs = []
    if os.path.exists(SLACK_CONFIGS_FILE):
        with open(SLACK_CONFIGS_FILE) as f:
            configs = json.load(f)

    if not configs:
        raise HTTPException(status_code=400, detail="未配置 Slack，请先在设置页添加")

    if config:
        targets = [c for c in configs if c["name"] == config]
        if not targets:
            raise HTTPException(status_code=404, detail=f"未找到配置: {config}")
    else:
        targets = configs

    ok = 0
    fail = 0
    errors = []
    for c in targets:
        err = _send_slack_report(c["token"], c["channel"], results, regime, confidence, adv_ratio)
        if err:
            fail += 1
            errors.append(f"{c['name']}: {err}")
        else:
            ok += 1

    if fail == 0:
        return {"message": f"报告已发送到 {ok} 个配置"}
    elif ok > 0:
        return {"message": f"部分成功: {ok} 成功, {fail} 失败", "errors": errors}
    raise HTTPException(status_code=500, detail=f"全部发送失败: {'; '.join(errors)}")


@router.post("/refresh")
def refresh_analysis():
    with _lock:
        if _status.get("status") == "running":
            return {"message": "分析已在运行中"}
    thread = threading.Thread(target=_run_analysis, daemon=True)
    thread.start()
    return {"message": "分析已开始"}


def _run_analysis():
    try:
        _save_status("running", 0, "开始分析...")
        result = analyze_stocks(NASDAQ100_STOCK_LIST)
        all_results = result.get("all_results", [])

        if not all_results:
            _save_status("error", 0, "分析结果为空")
            return

        regime = result.get("market_regime", "sideways")
        all_results = patch_results(all_results, regime, result.get("qqq_above_ma200", True))

        sorted_results = sorted(all_results, key=lambda x: x.get("composite_score", 0), reverse=True)
        for i, r in enumerate(sorted_results):
            r["rank"] = i + 1

        output_data = {
            "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "market_regime": regime,
            "model_confidence": result.get("model_confidence", 0.5),
            "advance_ratio": result.get("advance_ratio", 0.5),
            "recommended_position": result.get("recommended_position", 0.5),
            "strategy_name": "Topaz US Moon Accumulation + Liquidity Exit",
            "benchmark": "QQQ",
            "market_description": result.get("market_description", ""),
            "qqq_above_ma200": result.get("qqq_above_ma200", False),
            "total_stocks": len(sorted_results),
            "results": sorted_results,
        }

        os.makedirs(os.path.dirname(RESULT_FILE), exist_ok=True)
        with open(RESULT_FILE, "w", encoding="utf-8") as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)

        _save_status("done", 100, f"分析完成，共 {len(sorted_results)} 只股票")
    except Exception as e:
        _save_status("error", 0, str(e)[:200])
