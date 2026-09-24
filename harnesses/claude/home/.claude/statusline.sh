#!/bin/bash
INPUT=$(cat)

CTX=$(echo "$INPUT" | jq -r '.context_window.used_percentage // empty' | cut -d. -f1)
CACHE_WARM=$(echo "$INPUT" | jq -r '.prompt_cache.warm | select(. != null)')
CACHE_TTL=$(echo "$INPUT" | jq -r '.prompt_cache.ttl // empty')
CACHE_EXP=$(echo "$INPUT" | jq -r '.prompt_cache.expires_at // empty' | cut -d. -f1)
COST=$(echo "$INPUT" | jq -r '.cost.total_cost_usd // empty | select(. > 0)')
FIVE_H=$(echo "$INPUT" | jq -r '.rate_limits.five_hour.used_percentage // empty')
SEVEN_D=$(echo "$INPUT" | jq -r '.rate_limits.seven_day.used_percentage // empty')
RESETS_AT=$(echo "$INPUT" | jq -r '.rate_limits.five_hour.resets_at // empty')
SEVEN_D_RESETS_AT=$(echo "$INPUT" | jq -r '.rate_limits.seven_day.resets_at // empty')

OUT=""
add() { OUT="${OUT:+$OUT | }$1"; }

[ -n "$CTX" ]    && add "ctx: ${CTX}%"

if [ -n "$CACHE_WARM" ]; then
    LEFT=$(( ${CACHE_EXP:-0} - $(date +%s) ))
    if [ "$CACHE_WARM" = "true" ] && [ "$LEFT" -gt 0 ]; then
        add "cache: $(( (LEFT + 59) / 60 ))m${CACHE_TTL:+ ($CACHE_TTL)}"
    else
        add "cache: cold"
    fi
fi

if [ -n "$FIVE_H" ]; then
    if [ -n "$RESETS_AT" ]; then
        RESET_TIME=$(date -d "@${RESETS_AT}" '+%H:%M' 2>/dev/null)
        [ -n "$RESET_TIME" ] && add "5h: ${FIVE_H}% (resets $RESET_TIME)" || add "5h: ${FIVE_H}%"
    else
        add "5h: ${FIVE_H}%"
    fi
fi

if [ -n "$SEVEN_D" ]; then
    if [ -n "$SEVEN_D_RESETS_AT" ]; then
        SEVEN_D_RESET_TIME=$(date -d "@${SEVEN_D_RESETS_AT}" '+%a %H:%M' 2>/dev/null)
        [ -n "$SEVEN_D_RESET_TIME" ] && add "7d: ${SEVEN_D}% (resets $SEVEN_D_RESET_TIME)" || add "7d: ${SEVEN_D}%"
    else
        add "7d: ${SEVEN_D}%"
    fi
fi

if [ -n "$COST" ]; then
    COST_FMT=$(LC_NUMERIC=C printf '%.2f' "$COST")
    [ "$COST_FMT" != "0.00" ] && add "cost: \$$COST_FMT"
fi

echo "$OUT"
