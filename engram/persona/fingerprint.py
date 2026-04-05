"""Behavioral fingerprint — pure statistical analysis of messaging patterns.

No LLM calls. No API costs. Extracts quantifiable personality signals
that language models cannot infer from content alone.
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone

import numpy as np

from engram.models import DataChunk


@dataclass
class BehavioralFingerprint:
    """Quantified behavioral profile from messaging data."""

    # Message style
    total_messages: int = 0
    self_messages: int = 0
    avg_length: float = 0.0
    median_length: float = 0.0
    short_msg_pct: float = 0.0  # <5 chars
    long_msg_pct: float = 0.0   # >50 chars
    emoji_pct: float = 0.0

    # Temporal patterns
    hourly_distribution: dict[int, int] = field(default_factory=dict)
    weekday_distribution: dict[str, int] = field(default_factory=dict)
    peak_hour: int = 0
    peak_day: str = ""

    # Social patterns
    top_contacts: list[tuple[str, int]] = field(default_factory=list)
    unique_contacts: int = 0
    initiation_rate: float = 0.0  # % of messages that are yours

    # Response behavior
    median_response_sec: float = 0.0
    fast_reply_pct: float = 0.0   # <30s
    slow_reply_pct: float = 0.0   # >10min

    # Derived personality signals
    communication_style: str = ""   # "concise" / "expressive" / "balanced"
    social_type: str = ""           # "initiator" / "responder" / "balanced"
    chronotype: str = ""            # "night_owl" / "early_bird" / "balanced"
    response_type: str = ""         # "instant" / "thoughtful" / "delayed"

    def to_dict(self) -> dict:
        return {
            "message_style": {
                "total_messages": self.total_messages,
                "self_messages": self.self_messages,
                "avg_length": round(self.avg_length, 1),
                "median_length": round(self.median_length, 1),
                "short_msg_pct": round(self.short_msg_pct, 1),
                "long_msg_pct": round(self.long_msg_pct, 1),
                "emoji_pct": round(self.emoji_pct, 1),
                "communication_style": self.communication_style,
            },
            "temporal": {
                "hourly": self.hourly_distribution,
                "weekday": self.weekday_distribution,
                "peak_hour": self.peak_hour,
                "peak_day": self.peak_day,
                "chronotype": self.chronotype,
            },
            "social": {
                "top_contacts": [{"name": n, "count": c} for n, c in self.top_contacts[:10]],
                "unique_contacts": self.unique_contacts,
                "initiation_rate": round(self.initiation_rate, 1),
                "social_type": self.social_type,
            },
            "response": {
                "median_seconds": round(self.median_response_sec, 1),
                "fast_reply_pct": round(self.fast_reply_pct, 1),
                "slow_reply_pct": round(self.slow_reply_pct, 1),
                "response_type": self.response_type,
            },
        }

    def format_report(self) -> str:
        lines = [
            "## Behavioral Fingerprint",
            "",
            "### Communication Style",
            f"- Type: **{self.communication_style}**",
            f"- Average message: {self.avg_length:.0f} chars (median {self.median_length:.0f})",
            f"- Short messages (<5 chars): {self.short_msg_pct:.0f}%",
            f"- Emoji usage: {self.emoji_pct:.0f}% of messages",
            "",
            "### Temporal Pattern",
            f"- Chronotype: **{self.chronotype}**",
            f"- Peak hour: {self.peak_hour:02d}:00",
            f"- Most active day: {self.peak_day}",
            "",
            "### Social Pattern",
            f"- Type: **{self.social_type}**",
            f"- Unique contacts: {self.unique_contacts}",
            f"- Initiation rate: {self.initiation_rate:.0f}%",
            f"- Top contacts: {', '.join(n for n, _ in self.top_contacts[:5])}",
            "",
            "### Response Behavior",
            f"- Type: **{self.response_type}**",
            f"- Median response: {self.median_response_sec:.0f}s",
            f"- Fast replies (<30s): {self.fast_reply_pct:.0f}%",
            f"- Slow replies (>10min): {self.slow_reply_pct:.0f}%",
        ]
        return "\n".join(lines)


def analyze_fingerprint(chunks: list[DataChunk]) -> BehavioralFingerprint:
    """Compute behavioral fingerprint from DataChunks.

    Expects chunks with [我] / [other] speaker labels (from WeChatDBParser).
    Also works with Bilibili watch history chunks.
    """
    fp = BehavioralFingerprint()

    hours: Counter[int] = Counter()
    weekdays: Counter[str] = Counter()
    msg_lengths: list[int] = []
    contact_counts: Counter[str] = Counter()
    emoji_count = 0
    total_self = 0
    total_other = 0
    response_times: list[float] = []

    for chunk in chunks:
        if chunk.source == "wechat":
            _process_wechat_chunk(
                chunk, hours, weekdays, msg_lengths,
                contact_counts, response_times,
                total_self_ref=[0], total_other_ref=[0],
                emoji_ref=[0],
            )
            total_self += _last_self[0]
            total_other += _last_other[0]
            emoji_count += _last_emoji[0]
        elif chunk.source == "bilibili" or chunk.source == "youtube":
            # Watch history contributes to temporal patterns
            dt = chunk.timestamp
            hours[dt.hour] += 1
            weekdays[dt.strftime("%A")] += 1

    fp.total_messages = total_self + total_other
    fp.self_messages = total_self

    # Message style
    if msg_lengths:
        lens = np.array(msg_lengths)
        fp.avg_length = float(lens.mean())
        fp.median_length = float(np.median(lens))
        fp.short_msg_pct = sum(1 for l in lens if l < 5) * 100 / len(lens)
        fp.long_msg_pct = sum(1 for l in lens if l > 50) * 100 / len(lens)
        fp.emoji_pct = emoji_count * 100 / total_self if total_self else 0

    # Temporal
    fp.hourly_distribution = dict(hours)
    fp.weekday_distribution = dict(weekdays)
    if hours:
        fp.peak_hour = hours.most_common(1)[0][0]
    if weekdays:
        fp.peak_day = weekdays.most_common(1)[0][0]

    # Social
    fp.top_contacts = contact_counts.most_common(20)
    fp.unique_contacts = len(contact_counts)
    fp.initiation_rate = total_self * 100 / (total_self + total_other) if (total_self + total_other) else 0

    # Response
    if response_times:
        rt = np.array(response_times)
        fp.median_response_sec = float(np.median(rt))
        fp.fast_reply_pct = sum(1 for r in rt if r < 30) * 100 / len(rt)
        fp.slow_reply_pct = sum(1 for r in rt if r > 600) * 100 / len(rt)

    # Derive personality signals
    fp.communication_style = _classify_communication(fp)
    fp.social_type = _classify_social(fp)
    fp.chronotype = _classify_chronotype(fp)
    fp.response_type = _classify_response(fp)

    return fp


# --- Internal helpers ---

# Mutable refs for accumulation across chunks
_last_self: list[int] = [0]
_last_other: list[int] = [0]
_last_emoji: list[int] = [0]


def _process_wechat_chunk(
    chunk: DataChunk,
    hours: Counter,
    weekdays: Counter,
    msg_lengths: list,
    contact_counts: Counter,
    response_times: list,
    total_self_ref: list,
    total_other_ref: list,
    emoji_ref: list,
) -> None:
    global _last_self, _last_other, _last_emoji
    self_count = 0
    other_count = 0
    emoji_n = 0

    talker = chunk.metadata.get("talker", "unknown")
    base_ts = int(chunk.timestamp.timestamp()) if chunk.timestamp else 0

    lines = chunk.content.split("\n")
    last_other_ts = None
    line_offset = 0

    for line in lines:
        line = line.strip()
        if not line:
            continue

        is_self = line.startswith("[我]")
        is_other = not is_self and line.startswith("[")

        if is_self:
            content = line[3:].strip()  # Remove [我] prefix
            self_count += 1
            msg_lengths.append(len(content))
            contact_counts[talker] += 1

            # Approximate timestamp from position in chunk
            approx_ts = base_ts + line_offset * 30  # ~30s between messages
            dt = datetime.fromtimestamp(approx_ts, tz=timezone.utc)
            hours[dt.hour] += 1
            weekdays[dt.strftime("%A")] += 1

            # Emoji
            emoji_n += len(re.findall(r"\[.+?\]", content))

            # Response time
            if last_other_ts is not None:
                response_times.append(line_offset * 30)  # approximate
            last_other_ts = None
        elif is_other:
            other_count += 1
            last_other_ts = line_offset

        line_offset += 1

    _last_self = [self_count]
    _last_other = [other_count]
    _last_emoji = [emoji_n]


def _classify_communication(fp: BehavioralFingerprint) -> str:
    if fp.median_length < 8:
        return "concise"
    elif fp.median_length > 30:
        return "expressive"
    return "balanced"


def _classify_social(fp: BehavioralFingerprint) -> str:
    if fp.initiation_rate > 55:
        return "initiator"
    elif fp.initiation_rate < 35:
        return "responder"
    return "balanced"


def _classify_chronotype(fp: BehavioralFingerprint) -> str:
    if not fp.hourly_distribution:
        return "unknown"
    # Night hours (22-04) vs morning hours (06-12)
    night = sum(fp.hourly_distribution.get(h, 0) for h in [22, 23, 0, 1, 2, 3, 4])
    morning = sum(fp.hourly_distribution.get(h, 0) for h in [6, 7, 8, 9, 10, 11, 12])
    total = sum(fp.hourly_distribution.values())
    if total == 0:
        return "unknown"
    night_pct = night * 100 / total
    morning_pct = morning * 100 / total
    if night_pct > 35:
        return "night_owl"
    elif morning_pct > 50:
        return "early_bird"
    return "balanced"


def _classify_response(fp: BehavioralFingerprint) -> str:
    if fp.median_response_sec < 30:
        return "instant"
    elif fp.median_response_sec < 300:
        return "thoughtful"
    return "delayed"
