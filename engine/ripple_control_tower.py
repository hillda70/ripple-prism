from __future__ import annotations

import argparse
import csv
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple


@dataclass
class AssetRow:
    symbol: str
    last: Optional[float]
    ema20: Optional[float]
    ema50: Optional[float]
    high_3m: Optional[float]
    low_3m: Optional[float]
    iv_rank: Optional[float]
    term_skew: Optional[float]
    atrp9: Optional[float]
    atrp20: Optional[float]
    atrp_r: Optional[float]
    change: Optional[float]
    atr14: Optional[float]
    time: str


def to_float(value: str) -> Optional[float]:
    if value is None:
        return None
    s = str(value).strip()
    if not s or s.upper() in {"N/A", "#DIV/0!"}:
        return None
    s = s.replace("%", "")
    try:
        return float(s)
    except ValueError:
        return None


# Score helpers ---------------------------------------------------------------

def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def pct_below(reference: Optional[float], value: Optional[float]) -> float:
    if reference is None or value is None or reference == 0:
        return 0.0
    return max(0.0, (reference - value) / reference * 100.0)


def pct_above(reference: Optional[float], value: Optional[float]) -> float:
    if reference is None or value is None or reference == 0:
        return 0.0
    return max(0.0, (value - reference) / reference * 100.0)


def distance_to_low(low: Optional[float], last: Optional[float]) -> float:
    if low is None or last is None or low == 0:
        return 999.0
    return (last - low) / low * 100.0


def score_equity_pressure(row: AssetRow) -> float:
    score = 0.0
    score += clamp(pct_below(row.ema20, row.last) * 1.2, 0, 25)
    score += clamp(pct_below(row.ema50, row.last) * 1.0, 0, 20)

    dlow = distance_to_low(row.low_3m, row.last)
    if dlow <= 0.5:
        score += 25
    elif dlow <= 1.5:
        score += 18
    elif dlow <= 3.0:
        score += 10

    if row.iv_rank is not None:
        score += clamp((row.iv_rank - 20) * 0.35, 0, 20)
    if row.atrp_r is not None:
        score += clamp((row.atrp_r - 100) * 0.25, 0, 15)
    if row.change is not None and row.change < 0:
        score += clamp(abs(row.change) * 1.5, 0, 15)
    return round(clamp(score, 0, 100), 2)


def score_volatility(row: AssetRow) -> float:
    score = 0.0
    if row.iv_rank is not None:
        score += clamp((row.iv_rank - 15) * 0.7, 0, 50)
    if row.term_skew is not None:
        score += clamp((row.term_skew - 1.0) * 35, 0, 20)
    if row.atrp_r is not None:
        score += clamp((row.atrp_r - 90) * 0.4, 0, 30)
    return round(clamp(score, 0, 100), 2)


def score_defensive_bid(row: AssetRow) -> float:
    score = 0.0
    score += clamp(pct_above(row.ema20, row.last) * 8, 0, 25)
    score += clamp(pct_above(row.ema50, row.last) * 5, 0, 20)
    if row.change is not None and row.change > 0:
        score += clamp(row.change * 25, 0, 20)
    if row.iv_rank is not None:
        score += clamp((40 - row.iv_rank) * 0.75, 0, 20)
    if row.atrp_r is not None:
        score += clamp((115 - row.atrp_r) * 0.5, 0, 15)
    return round(clamp(score, 0, 100), 2)


def score_credit_stress(row: AssetRow) -> float:
    score = 0.0
    score += clamp(pct_below(row.ema20, row.last) * 15, 0, 25)
    score += clamp(pct_below(row.ema50, row.last) * 12, 0, 20)
    if row.iv_rank is not None:
        score += clamp((row.iv_rank - 10) * 0.8, 0, 30)
    if row.atrp_r is not None:
        score += clamp((row.atrp_r - 100) * 0.35, 0, 20)
    if row.change is not None and row.change < 0:
        score += clamp(abs(row.change) * 30, 0, 15)
    return round(clamp(score, 0, 100), 2)


def classify(score: float) -> str:
    if score < 25:
        return "GREEN"
    if score < 45:
        return "YELLOW"
    if score < 65:
        return "ORANGE"
    return "RED"


# IO -------------------------------------------------------------------------

def load_csv(path: Path) -> Dict[str, AssetRow]:
    out: Dict[str, AssetRow] = {}
    with path.open("r", newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for r in reader:
            symbol = (r.get("Symbol") or "").strip().upper()
            if not symbol:
                continue
            out[symbol] = AssetRow(
                symbol=symbol,
                last=to_float(r.get("Last", "")),
                ema20=to_float(r.get("20D EMA", "")),
                ema50=to_float(r.get("50D EMA", "")),
                high_3m=to_float(r.get("3M High", "")),
                low_3m=to_float(r.get("3M Low", "")),
                iv_rank=to_float(r.get("IV Rank", "")),
                term_skew=to_float(r.get("TERM_SKEW", "")),
                atrp9=to_float(r.get("9D ATRP", "")),
                atrp20=to_float(r.get("20D ATRP", "")),
                atrp_r=to_float(r.get("ATRP_R", "")),
                change=to_float(r.get("Change", "")),
                atr14=to_float(r.get("14D ATR", "")),
                time=r.get("Time", ""),
            )
    return out


def mean(values: List[float]) -> float:
    valid = [v for v in values if v is not None]
    return round(sum(valid) / len(valid), 2) if valid else 0.0


def summarize(data: Dict[str, AssetRow]) -> str:
    required = ["SPY", "QQQ", "IWM", "GLD", "XLP", "XLU", "HYG", "EWY", "EEM", "USO", "IBIT", "ETHA"]
    missing = [s for s in required if s not in data]
    if missing:
        raise ValueError(f"Missing required symbols: {', '.join(missing)}")

    zorb_scores = [score_equity_pressure(data[s]) for s in ["SPY", "QQQ", "IWM"]]
    vol_scores = [score_volatility(data[s]) for s in ["SPY", "EWY", "USO"]]
    anchor_scores = [score_defensive_bid(data[s]) for s in ["GLD", "XLP", "XLU"]]
    credit_score = score_credit_stress(data["HYG"])
    global_risk_scores = [score_volatility(data[s]) for s in ["EWY", "EEM"]]
    crypto_scores = [score_volatility(data[s]) for s in ["IBIT", "ETHA"]]

    zorb = mean(zorb_scores)
    vol = mean(vol_scores)
    anchor = mean(anchor_scores)
    global_risk = mean(global_risk_scores)
    crypto = mean(crypto_scores)

    # Overall state logic
    overall = round((zorb * 0.35) + (vol * 0.20) + (anchor * 0.15) + (credit_score * 0.15) + (global_risk * 0.10) + (crypto * 0.05), 2)

    spy = data["SPY"]
    spy_low_dist = distance_to_low(spy.low_3m, spy.last)
    event_horizon_note = "WATCH" if spy.last is not None and spy.last <= 660.0 else "ABOVE WATCH"
    if spy.last is not None and spy.last <= 657.0:
        event_horizon_note = "BREACH"

    lines = []
    lines.append("RIPPLE CONTROL TOWER")
    lines.append("=" * 72)
    lines.append(f"Timestamp: {spy.time or 'N/A'}")
    lines.append("")
    lines.append(f"1. ZORB PRESSURE      {zorb:>6.2f}   {classify(zorb)}")
    lines.append(f"   SPY={score_equity_pressure(data['SPY']):.2f}  QQQ={score_equity_pressure(data['QQQ']):.2f}  IWM={score_equity_pressure(data['IWM']):.2f}")
    lines.append(f"   SPY distance to 3M low: {spy_low_dist:.2f}%")
    lines.append("")
    lines.append(f"2. VOLATILITY ENGINE  {vol:>6.2f}   {classify(vol)}")
    lines.append(f"   SPY={score_volatility(data['SPY']):.2f}  EWY={score_volatility(data['EWY']):.2f}  USO={score_volatility(data['USO']):.2f}")
    lines.append("")
    lines.append(f"3. DIVERGENCE ANCHOR  {anchor:>6.2f}   {classify(anchor)}")
    lines.append(f"   GLD={score_defensive_bid(data['GLD']):.2f}  XLP={score_defensive_bid(data['XLP']):.2f}  XLU={score_defensive_bid(data['XLU']):.2f}")
    lines.append("")
    lines.append(f"4. CREDIT STRESS      {credit_score:>6.2f}   {classify(credit_score)}")
    lines.append(f"   HYG={credit_score:.2f}")
    lines.append("")
    lines.append(f"5. GLOBAL RISK        {global_risk:>6.2f}   {classify(global_risk)}")
    lines.append(f"   EWY={score_volatility(data['EWY']):.2f}  EEM={score_volatility(data['EEM']):.2f}")
    lines.append("")
    lines.append(f"6. CRYPTO BETA        {crypto:>6.2f}   {classify(crypto)}")
    lines.append(f"   IBIT={score_volatility(data['IBIT']):.2f}  ETHA={score_volatility(data['ETHA']):.2f}")
    lines.append("")
    lines.append(f"7. OVERALL STATE      {overall:>6.2f}   {classify(overall)}")

    if overall < 30:
        state = "STABLE / POSITIVE GAMMA BACKDROP"
    elif overall < 50:
        state = "STRUCTURAL TENSION BUILDING"
    elif overall < 65:
        state = "PRE-CASCADE / EVENT HORIZON APPROACHING"
    else:
        state = "NEGATIVE GAMMA CASCADE / ZORB ROLLING"
    lines.append(f"   {state}")
    lines.append("")
    lines.append("8. EVENT HORIZON WATCH")
    lines.append(f"   SPY last = {spy.last:.2f if spy.last is not None else float('nan')}")
    lines.append(f"   Threshold = 660.00")
    lines.append(f"   Status = {event_horizon_note}")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build an EOD RIPPLE Control Tower summary from a CSV export.")
    parser.add_argument("csv_path", help="Path to CSV file")
    parser.add_argument("--output", help="Optional path to save the summary text")
    args = parser.parse_args()

    data = load_csv(Path(args.csv_path))
    summary = summarize(data)
    print(summary)

    if args.output:
        Path(args.output).write_text(summary, encoding="utf-8")


if __name__ == "__main__":
    main()
