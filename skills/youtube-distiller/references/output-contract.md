# Output Contract

Use when converting a video distillation into structured JSON for a website,
search index, ranking system, study database, or downstream automation.

## Generic Distillation JSON

```json
{
  "video_id": "VIDEOID",
  "url": "https://youtube.com/watch?v=VIDEOID",
  "title": "",
  "channel": "",
  "duration_sec": 0,
  "user_requirement": "",
  "output_kind": "summary|qa|topic|tutorial|strategy|claims|notes|custom",
  "distillation_status": "complete_with_visual_extraction|visual_ocr_extracted_pending_vision_review|visual_sources_acquired_pending_interpretation|complete_transcript_only_visual_not_required|partial_missing_required_visual_evidence|source_unavailable",
  "source_status": {
    "transcript": "manual_captions|auto_captions|whisper|user_provided|missing",
    "visual": "available|missing_required|not_required",
    "fallback": "none|indexed_summary|user_artifact"
  },
  "answer": "",
  "key_points": [],
  "evidence": [
    {
      "type": "transcript|frame|indexed_summary|metadata",
      "timestamp_sec": 0,
      "path_or_url": "",
      "quote_or_note": ""
    }
  ],
  "missing_evidence": [],
  "confidence": "high|medium|low"
}
```

## Strategy Candidate JSON

Use only for trading/investing strategy extraction.

```json
{
  "strategy_id": "yt-VIDEOID-s1",
  "asset_class": "stocks|etf|crypto|forex|futures|options|mixed|unknown",
  "timeframe": "1m|5m|15m|1h|4h|1d|1wk|unknown",
  "direction": "long|short|both|unknown",
  "candidate_filters": [],
  "indicators": [],
  "entry_rules": [],
  "exit_rules": [],
  "stop_rules": [],
  "position_sizing": [],
  "evidence": [],
  "backtest_status": "backable|partially_backable_needs_visual_verification|not_backable",
  "missing_details": []
}
```

## Backtest Readiness Checklist

A strategy is `backable` only when these are explicit:

- instrument universe
- timeframe
- data source
- entry trigger
- exit trigger
- stop rule
- take-profit or trailing rule
- position sizing
- transaction cost/slippage assumptions
- whether signals execute intrabar, at close, or next open
