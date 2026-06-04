#!/usr/bin/env bash
# web-searcher: Multi-engine parallel web search via curl
# Usage: bash search.sh "query" [--engines bing,google] [--limit 10] [--json] [--lang en|zh]
# Dependencies: curl, grep -P (PCRE), sed, base64

set -uo pipefail

QUERY="" ENGINES="bing,google,duckduckgo,sogou" LIMIT=10 JSON_OUT=0 LANG_OPT="en"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --engines|-e) ENGINES="$2"; shift 2 ;;
    --limit|-l)   LIMIT="$2"; shift 2 ;;
    --json|-j)    JSON_OUT=1; shift ;;
    --lang)       LANG_OPT="$2"; shift 2 ;;
    --help|-h)
      echo "Usage: bash search.sh \"query\" [--engines bing,google,sogou] [--limit 10] [--json] [--lang en|zh]"
      exit 0 ;;
    -*) echo "Unknown option: $1" >&2; exit 1 ;;
    *)  QUERY="$1"; shift ;;
  esac
done

[[ -z "$QUERY" ]] && { echo "Error: No query provided." >&2; exit 1; }
[[ "$LANG_OPT" == "zh" && "$ENGINES" != *"baidu"* ]] && ENGINES="$ENGINES,baidu"

urlencode() {
  local str="$1" out="" c i
  for (( i=0; i<${#str}; i++ )); do
    c="${str:$i:1}"
    case "$c" in
      [a-zA-Z0-9.~_-]) out+="$c" ;;
      ' ') out+="%20" ;;
      *) printf -v hex '%%%02X' "'$c" 2>/dev/null && out+="$hex" || out+="$c" ;;
    esac
  done
  echo "$out"
}

ENCODED_QUERY=$(urlencode "$QUERY")

b64decode() {
  local input="$1"
  local mod=$(( ${#input} % 4 ))
  [[ $mod -eq 2 ]] && input="${input}=="
  [[ $mod -eq 3 ]] && input="${input}="
  input=$(echo "$input" | tr '_-' '/+')
  echo "$input" | base64 -d 2>/dev/null || echo ""
}

htmldec() {
  echo "$1" | sed 's/&amp;/\&/g;s/&lt;/</g;s/&gt;/>/g;s/&quot;/"/g;s/&#39;/'"'"'/g;s/&nbsp;/ /g;s/<[^>]*>//g' | sed 's/^[[:space:]]*//;s/[[:space:]]*$//'
}

TMPDIR=$(mktemp -d 2>/dev/null || mktemp -d -t ws)
trap 'rm -rf "$TMPDIR"' EXIT

fetch_engine() {
  local engine="$1" url html flat
  case "$engine" in
    bing)       url="https://www.bing.com/search?q=${ENCODED_QUERY}" ;;
    google)     url="https://www.google.com/search?q=${ENCODED_QUERY}" ;;
    duckduckgo) url="https://html.duckduckgo.com/html/?q=${ENCODED_QUERY}" ;;
    baidu)      url="https://www.baidu.com/s?wd=${ENCODED_QUERY}" ;;
    sogou)      url="https://www.sogou.com/web?query=${ENCODED_QUERY}" ;;
    *) return ;;
  esac

  html=$(curl -sL --max-time 15 \
    -H "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36" \
    -H "Accept-Language: en-US,en;q=0.9" \
    "$url" 2>/dev/null) || return

  flat=$(echo "$html" | tr -d '\n\r')

  case "$engine" in
    bing)
      echo "$flat" | grep -oP '<h2 class="">.*?</h2>\s*<div class="b_caption">.*?</div>' 2>/dev/null | head -n "$LIMIT" | while IFS= read -r block; do
        local b64url real_url title snippet
        b64url=$(echo "$block" | grep -oP 'u=a1\K[A-Za-z0-9+/=_-]+' 2>/dev/null | head -1)
        [[ -z "$b64url" ]] && continue
        real_url=$(b64decode "$b64url")
        [[ -z "$real_url" ]] && continue
        echo "$real_url" | grep -qiE '^https?://(www\.)?(bing|microsoft)\.com/search' && continue

        title=$(echo "$block" | grep -oP '<a[^>]*>\K.*?(?=</a>)' 2>/dev/null | head -1 | sed 's/<[^>]*>//g')
        title=$(htmldec "$title")
        [[ -z "$title" ]] && title=$(echo "$real_url" | sed 's|https\?://||;s|/.*||')

        snippet=$(echo "$block" | grep -oP 'b_lineclamp\d+">.*?</p>' 2>/dev/null | head -1 | sed 's/b_lineclamp[0-9]*">//;s/<\/p>//;s/<[^>]*>//g')
        snippet=$(htmldec "$snippet")

        echo "${title}|||${real_url}|||${snippet}"
      done
      ;;

    google)
      echo "$flat" | grep -oP 'href="/url\?q=\Khttps?://[^&"]+' 2>/dev/null | head -n "$LIMIT" | while IFS= read -r raw_url; do
        raw_url=$(echo "$raw_url" | sed 's/%3A/:/g;s/%2F/\//g;s/%3F/?/g;s/%3D/=/g;s/%26/\&/g;s/+/ /g')
        echo "$raw_url" | grep -qiE 'google\.com/search|youtube\.com/results' && continue
        local title
        title=$(echo "$raw_url" | sed 's|https\?://||;s|/.*||')
        echo "${title}|||${raw_url}|||"
      done
      ;;

    duckduckgo)
      echo "$flat" | grep -oP 'class="result__a"[^>]*href="\Khttps?://[^"]+' 2>/dev/null | head -n "$LIMIT" | while IFS= read -r url; do
        echo "$url" | grep -qiE 'duckduckgo\.com' && continue
        local title
        title=$(echo "$flat" | grep -oP "href=\"${url}\"[^>]*>\K[^<]+" 2>/dev/null | head -1)
        title=$(htmldec "$title")
        [[ -z "$title" ]] && title=$(echo "$url" | sed 's|https\?://||;s|/.*||')
        echo "${title}|||${url}|||"
      done
      ;;

    baidu)
      echo "$flat" | grep -oP '<h3[^>]*class="t"[^>]*>\s*<a[^>]*href="\Khttps?://[^"]+' 2>/dev/null | head -n "$LIMIT" | while IFS= read -r url; do
        local title
        title=$(echo "$flat" | grep -oP "href=\"${url}\"[^>]*>\K[^<]+" 2>/dev/null | head -1)
        title=$(htmldec "$title")
        [[ -z "$title" ]] && continue
        echo "${title}|||${url}|||"
      done
      ;;

    sogou)
      # Sogou: <h3 class="vr-title">...<a href="/link?url=...">title</a>...</h3>
      echo "$flat" | grep -oP '<h3 class="vr-title.*?</h3>' 2>/dev/null | head -n "$LIMIT" | while IFS= read -r block; do
        # Skip ads (blocks without <a> tag)
        echo "$block" | grep -q '<a ' || continue
        local raw_url title
        raw_url=$(echo "$block" | grep -oP 'href="\K[^"]+' | head -1)
        [[ -z "$raw_url" ]] && continue
        # Convert relative /link?url= to absolute
        if [[ "$raw_url" == /link* ]]; then
          raw_url="https://www.sogou.com${raw_url}"
        fi
        # Extract title: text inside <a>, strip <em> and other tags
        title=$(echo "$block" | grep -oP '<a[^>]*>\K.*?(?=</a>)' | head -1 | sed 's/<[^>]*>//g;s/<!--[^>]*-->//g')
        title=$(htmldec "$title")
        # Clean up whitespace
        title=$(echo "$title" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
        [[ -z "$title" ]] && continue
        echo "${title}|||${raw_url}|||"
      done
      ;;
  esac
}

# ── Parallel fetch ───────────────────────────────────────────────
PIDS=()
IFS=',' read -ra ENGINE_LIST <<< "$ENGINES"

for engine in "${ENGINE_LIST[@]}"; do
  engine=$(echo "$engine" | tr '[:upper:]' '[:lower:]' | xargs)
  case "$engine" in
    bing|google|duckduckgo|baidu|sogou)
      fetch_engine "$engine" > "$TMPDIR/${engine}.txt" 2>/dev/null &
      PIDS+=($!)
      ;;
    *) echo "Warning: Unknown engine '$engine'" >&2 ;;
  esac
done

for pid in "${PIDS[@]}"; do wait "$pid" 2>/dev/null || true; done

# ── Merge & deduplicate ─────────────────────────────────────────
declare -A SEEN
ALL="" TOTAL=0

for engine in "${ENGINE_LIST[@]}"; do
  engine=$(echo "$engine" | tr '[:upper:]' '[:lower:]' | xargs)
  f="$TMPDIR/${engine}.txt"
  [[ ! -f "$f" ]] && continue

  while IFS= read -r line; do
    [[ -z "$line" ]] && continue
    title="${line%%|||*}"
    rest="${line#*|||}"
    url="${rest%%|||*}"
    snippet="${rest#*|||}"
    url=$(echo "$url" | xargs)
    [[ -z "$url" ]] && continue

    key=$(echo "$url" | sed 's|https\?://||;s|^[^/]*||;s|\?.*||;s|#.*||')
    [[ -n "${SEEN[$key]+x}" ]] && continue
    SEEN[$key]=1

    ALL+="${title}|||${url}|||${snippet}"$'\n'
    TOTAL=$((TOTAL + 1))
  done < "$f"
done

# ── Output ───────────────────────────────────────────────────────
if [[ "$JSON_OUT" -eq 1 ]]; then
  echo "["
  FIRST=1
  while IFS= read -r line; do
    [[ -z "$line" ]] && continue
    title="${line%%|||*}"; rest="${line#*|||}"; url="${rest%%|||*}"; snippet="${rest#*|||}"
    [[ "$FIRST" -eq 0 ]] && echo ","
    title=$(echo "$title" | sed 's/\\/\\\\/g;s/"/\\"/g')
    url=$(echo "$url" | sed 's/\\/\\\\/g;s/"/\\"/g')
    snippet=$(echo "$snippet" | sed 's/\\/\\\\/g;s/"/\\"/g')
    echo "  {\"title\": \"$title\", \"url\": \"$url\", \"snippet\": \"$snippet\"}"
    FIRST=0
  done <<< "$ALL"
  echo "]"
else
  echo ""
  echo "=== Search Results: \"$QUERY\" ==="
  echo "Found $TOTAL results from: ${ENGINES}"
  echo ""
  NUM=1
  while IFS= read -r line; do
    [[ -z "$line" ]] && continue
    title="${line%%|||*}"; rest="${line#*|||}"; url="${rest%%|||*}"; snippet="${rest#*|||}"
    echo "$NUM. $title"
    echo "   $url"
    [[ -n "$snippet" ]] && echo "   $snippet"
    echo ""
    NUM=$((NUM + 1))
  done <<< "$ALL"
fi
