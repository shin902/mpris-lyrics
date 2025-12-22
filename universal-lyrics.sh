#!/bin/bash
# 汎用歌詞取得スクリプト (Universal Lyrics Fetcher)
# Usage: ./script.sh [--target <player>] [--format <json|text|raw>]

CACHE_DIR="/tmp/lyrics_cache"
mkdir -p "$CACHE_DIR"

# デフォルト設定
TARGET_PLAYER=""
OUTPUT_FORMAT="json" # json (Eww), text (CLI), raw (LRC content)
PLAYER_ORDER=("brave" "spotify")

# --- 引数解析 ---
while [[ "$#" -gt 0 ]]; do
    case $1 in
        --target) TARGET_PLAYER="$2"; shift ;;
        --format) OUTPUT_FORMAT="$2"; shift ;;
        *) echo "Unknown parameter: $1"; exit 1 ;;
    esac
    shift
done

# --- 関数定義 ---

# .lrc形式のタイムスタンプを秒に変換
parse_timestamp() {
    local timestamp="$1"
    timestamp=$(echo "$timestamp" | tr -d '[]')
    local minutes=$(echo "$timestamp" | cut -d':' -f1)
    local seconds=$(echo "$timestamp" | cut -d':' -f2)
    echo "$minutes $seconds" | awk '{print $1 * 60 + $2}'
}

detect_player() {
    local p_name="$1"
    local status=$(playerctl -p "$p_name" status 2>/dev/null)
    if [ "$status" = "Playing" ] || [ "$status" = "Paused" ]; then
        echo "$p_name"
        return 0
    fi
    return 1
}

# --- プレイヤー決定 ---
PLAYER=""
STATUS="Stopped"

if [ -n "$TARGET_PLAYER" ]; then
    # ターゲット指定がある場合、そのプレイヤーのみチェック
    ACTUAL_PLAYER=$(playerctl -l 2>/dev/null | grep -i "$TARGET_PLAYER" | head -n1)
    if [ -n "$ACTUAL_PLAYER" ]; then
        if detect_player "$ACTUAL_PLAYER" >/dev/null;
 then
            PLAYER="$ACTUAL_PLAYER"
            STATUS=$(playerctl -p "$PLAYER" status 2>/dev/null)
        fi
    fi
else
    # 自動検出 (優先順位順)
    for p in "${PLAYER_ORDER[@]}"; do
        ACTUAL_PLAYER=$(playerctl -l 2>/dev/null | grep -i "$p" | head -n1)
        if [ -n "$ACTUAL_PLAYER" ]; then
            if detect_player "$ACTUAL_PLAYER" >/dev/null;
 then
                PLAYER="$ACTUAL_PLAYER"
                STATUS=$(playerctl -p "$PLAYER" status 2>/dev/null)
                break
            fi
        fi
    done
fi

# 再生中のプレイヤーが見つからない場合
if [ -z "$PLAYER" ] || { [ "$STATUS" != "Playing" ] && [ "$STATUS" != "Paused" ]; }; then
    if [ "$OUTPUT_FORMAT" == "json" ]; then
        echo '{"status":"stopped","lines":[]}'
    elif [ "$OUTPUT_FORMAT" == "waybar" ]; then
        echo '{"text":"","class":"hidden","tooltip":"No active player"}'
    else
        echo "No active player found."
    fi
    exit 0
fi

# --- メタデータ取得 ---
ARTIST=$(playerctl -p "$PLAYER" metadata xesam:artist 2>/dev/null)
TITLE=$(playerctl -p "$PLAYER" metadata xesam:title 2>/dev/null)
ALBUM=$(playerctl -p "$PLAYER" metadata xesam:album 2>/dev/null)
POSITION=$(playerctl -p "$PLAYER" position 2>/dev/null)
LENGTH=$(playerctl -p "$PLAYER" metadata mpris:length 2>/dev/null)
LENGTH_SEC=""
[ -n "$LENGTH" ] && LENGTH_SEC=$((LENGTH / 1000000))
[ -z "$POSITION" ] && POSITION=0

# --- タイトル調整 (YouTube等向け) ---
if [[ "$PLAYER" != *"spotify"* ]]; then
    # 「 / 」で分割して前半部分のみを使用（YouTube形式: "曲名 / アーティスト"）
    if [[ "$TITLE" == *" / "* ]]; then
        CLEAN_TITLE=$(echo "$TITLE" | awk -F ' / ' '{print $1}')
    else
        CLEAN_TITLE="$TITLE"
    fi

    # 『』が含まれている場合、最初の『』の中身を抽出する
    if echo "$CLEAN_TITLE" | grep -q "『.*』"; then
        CLEAN_TITLE=$(echo "$CLEAN_TITLE" | sed -E 's/^[^『]*『([^』]+)』.*/\1/')
    fi

    # 括弧内の情報を削除 (Official Video, feat情報など)
    CLEAN_TITLE=$(echo "$CLEAN_TITLE" | sed -E 's/\([^)]*\)//g; s/\[[^]]*\]//g; s/【[^】]*】//g')

    # feat., ft. 表記を削除（括弧外にある場合）
    CLEAN_TITLE=$(echo "$CLEAN_TITLE" | sed -E 's/(feat\.|ft\.|featuring).*//I')

    # 特殊記号『』「」を削除
    CLEAN_TITLE=$(echo "$CLEAN_TITLE" | sed -E 's/[『』「」]//g')

    # 前後の空白削除
    CLEAN_TITLE=$(echo "$CLEAN_TITLE" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')

    # "Artist - Title" 形式の判定
    if [[ "$CLEAN_TITLE" == *" - "* ]]; then
        TEMP_ARTIST=$(echo "$CLEAN_TITLE" | awk -F " - " '{print $1}')
        TEMP_TITLE=$(echo "$CLEAN_TITLE" | awk -F " - " '{print $2}')
        if [ -n "$TEMP_ARTIST" ] && [ ${#TEMP_ARTIST} -lt 50 ]; then
            ARTIST="$TEMP_ARTIST"
            TITLE="$TEMP_TITLE"
        else
            TITLE="$CLEAN_TITLE"
        fi
    else
        TITLE="$CLEAN_TITLE"
    fi
    TRACK_KEY=$(echo "${ARTIST}${TITLE}" | md5sum | cut -d' ' -f1)
else
    TRACK_KEY=$(playerctl -p "$PLAYER" metadata mpris:trackid 2>/dev/null | sed 's|.*/||')
fi

if [ -z "$TITLE" ]; then
    if [ "$OUTPUT_FORMAT" == "json" ]; then
        echo '{"status":"no_info","lines":[]}'
    elif [ "$OUTPUT_FORMAT" == "waybar" ]; then
        echo '{"text":"","class":"hidden","tooltip":"No track info"}'
    else
        echo "No track info available."
    fi
    exit 0
fi

CACHE_FILE="$CACHE_DIR/${TRACK_KEY}.lrc"

# --- 歌詞取得・キャッシュ ---
if [ ! -f "$CACHE_FILE" ]; then
    FOUND=0
    # Spotify get API
    if [[ "$PLAYER" == *"spotify"* ]] && [ -n "$ARTIST" ] && [ -n "$ALBUM" ]; then
        response=$(curl -s -G "https://lrclib.net/api/get" \
            --data-urlencode "artist_name=$ARTIST" \
            --data-urlencode "track_name=$TITLE" \
            --data-urlencode "album_name=$ALBUM" \
            --data-urlencode "duration=$LENGTH_SEC")
        synced_lyrics=$(echo "$response" | jq -r '.syncedLyrics // empty' 2>/dev/null)
        if [ -n "$synced_lyrics" ] && [ "$synced_lyrics" != "null" ]; then
            echo "$synced_lyrics" > "$CACHE_FILE"
            FOUND=1
        fi
    fi

    # Search API
    if [ $FOUND -eq 0 ]; then
        # First try: Artist + Title
        SEARCH_QUERY="${ARTIST} ${TITLE}"
        [ -z "$SEARCH_QUERY" ] || [ "$SEARCH_QUERY" == " " ] && SEARCH_QUERY="$TITLE"
        search_response=$(curl -s -G "https://lrclib.net/api/search" --data-urlencode "q=$SEARCH_QUERY")
        result_count=$(echo "$search_response" | jq -r 'length')

        # Fallback: Title only if no results (for YouTube with long artist names)
        if [ "$result_count" = "0" ] && [ -n "$TITLE" ] && [ -n "$ARTIST" ]; then
            SEARCH_QUERY="$TITLE"
            search_response=$(curl -s -G "https://lrclib.net/api/search" --data-urlencode "q=$SEARCH_QUERY")
        fi

        first_synced=$(echo "$search_response" | jq -r '[.[] | select(.syncedLyrics != null)] | .[0].syncedLyrics // empty')

        if [ -n "$first_synced" ]; then
            echo "$first_synced" > "$CACHE_FILE"
        else
            first_plain=$(echo "$search_response" | jq -r '[.[] | select(.plainLyrics != null)] | .[0].plainLyrics // empty')
            if [ -n "$first_plain" ]; then
                echo "$first_plain" > "$CACHE_FILE"
            else
                touch "$CACHE_FILE"
            fi
        fi
    fi
fi

if [ ! -s "$CACHE_FILE" ]; then
    if [ "$OUTPUT_FORMAT" == "json" ]; then
        echo '{"status":"no_lyrics","lines":[]}'
    elif [ "$OUTPUT_FORMAT" == "waybar" ]; then
        echo '{"text":"","class":"hidden","tooltip":"No lyrics found"}'
    else
        echo "Lyrics not found for: $ARTIST - $TITLE"
    fi
    exit 0
fi

# --- 出力処理 ---

if [ "$OUTPUT_FORMAT" == "raw" ]; then
    cat "$CACHE_FILE"
    exit 0
fi

mapfile -t all_lyrics < "$CACHE_FILE"
is_synced=0
grep -qE "^\[[0-9]+:[0-9]+" "$CACHE_FILE" && is_synced=1

if [ "$OUTPUT_FORMAT" == "text" ]; then
    echo "Now Playing: $TITLE - $ARTIST ($PLAYER)"
    echo "----------------------------------------"
    for i in "${!all_lyrics[@]}"; do
        line="${all_lyrics[$i]}"
        text=$(echo "$line" | sed 's/^[[^]]*] //')
        is_current=0
        if [[ "$line" =~ ^\[[0-9]+:([0-9]+\.[0-9]+)\] ]]; then
            line_time=$(parse_timestamp "${BASH_REMATCH[0]}")
            next_time=99999
            if [ $((i+1)) -lt ${#all_lyrics[@]} ]; then
                next_line="${all_lyrics[$((i+1))]}"
                if [[ "$next_line" =~ ^\[[0-9]+:([0-9]+\.[0-9]+)\] ]]; then
                    next_time=$(parse_timestamp "${BASH_REMATCH[0]}")
                fi
            fi
            if [ $(echo "$POSITION $line_time $next_time" | awk '{if ($1 >= $2 && $1 < $3) print 1; else print 0}') -eq 1 ]; then
                is_current=1
            fi
        fi
        [ $is_current -eq 1 ] && echo "--> $text" || echo "    $text"
    done
    exit 0
fi

if [ "$OUTPUT_FORMAT" == "waybar" ]; then
    # Waybar用JSON出力 (tooltip形式)
    tooltip_lines=()
    current_lyric=""

    if [ $is_synced -eq 1 ]; then
        current_index=-1
        for i in "${!all_lyrics[@]}"; do
            line="${all_lyrics[$i]}"
            if [[ "$line" =~ ^\[[0-9]+:([0-9]+\.[0-9]+)\] ]]; then
                line_time=$(parse_timestamp "${BASH_REMATCH[0]}")
                next_time=99999
                if [ $((i+1)) -lt ${#all_lyrics[@]} ]; then
                    next_line="${all_lyrics[$((i+1))]}"
                    if [[ "$next_line" =~ ^\[[0-9]+:([0-9]+\.[0-9]+)\] ]]; then
                        next_time=$(parse_timestamp "${BASH_REMATCH[0]}")
                    fi
                fi
                if [ $(echo "$POSITION $line_time $next_time" | awk '{if ($1 >= $2 && $1 < $3) print 1; else print 0}') -eq 1 ]; then
                    current_index=$i
                    break
                fi
            fi
        done

        if [ $current_index -ge 0 ]; then
            start=$((current_index - 2))
            end=$((current_index + 2))
            [ $start -lt 0 ] && start=0
            [ $end -ge ${#all_lyrics[@]} ] && end=$((${#all_lyrics[@]} - 1))

            for ((i=start; i<=end; i++)); do
                lyric_text=$(echo "${all_lyrics[$i]}" | sed 's/^\[[^]]*\] //')

                # 空行処理: 現在行なら♪を表示、それ以外はスキップ
                if [ -z "$lyric_text" ] || [[ "$lyric_text" =~ ^[[:space:]]*$ ]]; then
                    if [ $i -eq $current_index ]; then
                        lyric_text="♪"
                    else
                        continue
                    fi
                fi

                if [ $i -eq $current_index ]; then
                    tooltip_lines+=("▶ $lyric_text")
                    current_lyric="$lyric_text"
                else
                    tooltip_lines+=("  $lyric_text")
                fi
            done
        fi
    else
        # 非同期歌詞
        count=0
        for line in "${all_lyrics[@]}"; do
            [ $count -ge 20 ] && tooltip_lines+=("... (以下省略)") && break
            tooltip_lines+=("$line")
            ((count++))
        done
        current_lyric="" # 非同期の場合はバーには表示しない（またはタイトルなどを表示）
    fi

    if [ ${#tooltip_lines[@]} -eq 0 ]; then
        tooltip="♪"
    else
        tooltip=$(printf "%s\n" "${tooltip_lines[@]}")
    fi

    # 表示テキストの作成（アイコン + 現在の歌詞）
    if [ -n "$current_lyric" ]; then
        display_text="󰎆 $current_lyric"
    else
        display_text="󰎆"
    fi

    # JSONエスケープ処理
    # 改行を含むtooltipと、特殊文字を含む可能性のあるtextを安全にエスケープ
    tooltip_escaped=$(echo "$tooltip" | jq -Rs .)
    text_escaped=$(echo "$display_text" | jq -Rs .)

    # 末尾の改行がjqによってエスケープされて "\n" として入ってしまう場合があるため、
    # 必要に応じて整形（jq -Rs . は入力の末尾の改行も文字列として含むため）
    # ただしWaybarは文字列としての "\n" を改行として扱わない（textフィールドの場合）ので、
    # textフィールドの末尾の改行は削除したい。

    # jq -R . (slurpなし) だと一行ごとに処理されるが、tooltipは複数行ありうる。
    # ここではシンプルに、jqが出力した "..." という文字列をそのまま埋め込む方式にする。
    # jq -Rs . の出力は常にダブルクォートで囲まれている。

    # text_escaped の末尾の改行(\n)削除 (jq -Rs . は末尾に改行がある場合それもエスケープする)
    # echo "$display_text" | jq -Rs . だと、echoがつけた改行も含まれる可能性があるため、
    # printf を使うか、jqの結果から除去する。

    text_escaped=$(printf "%s" "$display_text" | jq -Rs .)

    # tooltipは改行を含んでいて良い
    tooltip_escaped=$(printf "%s" "$tooltip" | jq -Rs .)

    echo "{\"text\":$text_escaped,\"class\":\"visible\",\"tooltip\":$tooltip_escaped}"
    exit 0
fi

if [ "$OUTPUT_FORMAT" == "json" ]; then
    if [ $is_synced -eq 1 ]; then
        current_index=-1
        for i in "${!all_lyrics[@]}"; do
            line="${all_lyrics[$i]}"
            if [[ "$line" =~ ^\[[0-9]+:([0-9]+\.[0-9]+)\] ]]; then
                line_time=$(parse_timestamp "${BASH_REMATCH[0]}")
                next_time=99999
                if [ $((i+1)) -lt ${#all_lyrics[@]} ]; then
                    next_line="${all_lyrics[$((i+1))]}"
                    if [[ "$next_line" =~ ^\[[0-9]+:([0-9]+\.[0-9]+)\] ]]; then
                        next_time=$(parse_timestamp "${BASH_REMATCH[0]}")
                    fi
                fi
                if [ $(echo "$POSITION $line_time $next_time" | awk '{if ($1 >= $2 && $1 < $3) print 1; else print 0}') -eq 1 ]; then
                    current_index=$i
                    break
                fi
            fi
        done
        [ $current_index -lt 0 ] && current_index=0

        start=$((current_index - 3))
        end=$((current_index + 3))
        [ $start -lt 0 ] && start=0
        [ $end -ge ${#all_lyrics[@]} ] && end=$((${#all_lyrics[@]} - 1))

        json_lines="["
        first=true
        for ((i=start; i<=end; i++)); do
            lyric_text=$(echo "${all_lyrics[$i]}" | sed 's/^\[[^]]*\] //')
            if [ -n "$lyric_text" ]; then
                lyric_text=$(echo "$lyric_text" | sed 's/\\/\\\\/g; s/"/\\"/g')
                [ "$first" = true ] && first=false || json_lines+=","
                is_curr="false"
                [ $i -eq $current_index ] && is_curr="true"
                json_lines+="{\"text\":\"$lyric_text\",\"current\":$is_curr}"
            fi
        done
        json_lines+="]"
        echo "{\"status\":\"ok\",\"lines\":$json_lines}"
    else
        json_lines="["
        first=true
        count=0
        for line in "${all_lyrics[@]}"; do
            [ $count -ge 10 ] && break
            if [ -n "$line" ]; then
                lyric_text=$(echo "$line" | sed 's/\\/\\\\/g; s/"/\\"/g')
                [ "$first" = true ] && first=false || json_lines+=","
                json_lines+="{\"text\":\"$lyric_text\",\"current\":false}"
                ((count++))
            fi
        done
        json_lines+="]"
        echo "{\"status\":\"ok\",\"lines\":$json_lines}"
    fi
fi
