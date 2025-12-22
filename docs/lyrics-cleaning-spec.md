# 曲名・アーティスト名のクリーニング処理 完全ドキュメント

**ファイルパス**: `/home/shi/ghq/github.com/shin902/mpris-lyrics/universal_lyrics.py`

---

## 目次
1. [グローバル定数: アーティスト名マッピング](#1-グローバル定数-アーティスト名マッピング)
2. [関数: clean_title() - タイトルのクリーニング](#2-関数-clean_title---タイトルのクリーニング)
3. [関数: get_lyrics() - 検索クエリ生成時のアーティスト名処理](#3-関数-get_lyrics---検索クエリ生成時のアーティスト名処理)

---

## 1. グローバル定数: アーティスト名マッピング

### 場所
- **行数**: 36-42行目
- **定数名**: `ARTIST_SEARCH_MAPPINGS`

### 実装内容
```python
# Artist name mappings for search queries
# Maps full artist names to preferred search names
ARTIST_SEARCH_MAPPINGS = {
    "ずっと真夜中でいいのに。 ZUTOMAYO": "ずっと真夜中でいいのに。",
    # Add more artist mappings here as needed
    # "Full Artist Name": "Preferred Search Name",
}
```

### 目的
特定のアーティスト名を検索時に別の形式に変換するためのマッピング辞書。

### 使用例
- キー: playerctlから取得した完全なアーティスト名
- 値: syncedlyricsで検索する際に使用する望ましいアーティスト名

### 拡張方法
新しいアーティストを追加する場合、辞書に新しいエントリを追加:
```python
ARTIST_SEARCH_MAPPINGS = {
    "ずっと真夜中でいいのに。 ZUTOMAYO": "ずっと真夜中でいいのに。",
    "YOASOBI": "YOASOBI",
    "米津玄師 Kenshi Yonezu": "米津玄師",
}
```

---

## 2. 関数: clean_title() - タイトルのクリーニング

### 場所
- **行数**: 100-161行目
- **関数名**: `clean_title(title: str, artist: str, player: str) -> tuple[str, str]`

### 目的
playerctlから取得した生のタイトル文字列から、不要な要素を除去してクリーンな曲名とアーティスト名を抽出する。

### パラメータ
- `title` (str): playerctlから取得した生のタイトル文字列
- `artist` (str): playerctlから取得した生のアーティスト文字列
- `player` (str): プレイヤー名（"spotify", "brave"など）

### 戻り値
- `tuple[str, str]`: (クリーンなタイトル, 抽出されたアーティスト名)

---

### 処理フロー詳細

#### 2.1. 初期化
```python
extracted_artist = ""
original_title = title  # Keep original for comparison
```
- 抽出アーティスト名を空文字列で初期化
- 元のタイトルをバックアップ

#### 2.2. 特定アーティストの特別処理（ずっと真夜中でいいのに。等）
```python
# Special handling for specific artists
# For artists like ZUTOMAYO, extract content from 『』 and preserve inner brackets like 「」
if "ずっと真夜中でいいのに。 ZUTOMAYO" in artist:
    if "『" in title and "』" in title:
        match = re.search(r"『([^』]+)』", title)
        if match:
            return match.group(1), extracted_artist
```
**処理内容**:
- 特定のアーティスト（例：「ずっと真夜中でいいのに。」）の場合、『』の中身を抽出し、**即座にリターン**する。
- これにより、後続の括弧削除や特殊引用符削除の処理を回避し、タイトル内の「」などを保持する。
- 例: `ずっと真夜中でいいのに。『Dear. Mr「F」』MV` -> `Dear. Mr「F」`

#### 2.3. Spotify専用処理
```python
if "spotify" in player.lower():
    # Remove feat./ft./featuring patterns (括弧内外両方)
    # ... (省略) ...
    return title, extracted_artist
```

**処理内容**:
- Spotifyの場合、feat./ft./featuring のみ削除
- 括弧内のfeat./ft./featuring を削除
- 括弧外のfeat./ft./featuring とそれ以降を削除
- 連続スペースを単一スペースに正規化
- **アーティスト名は抽出せず空文字列を返す**

---

#### 2.4. ハイフンの正規化
```python
# Normalize various dashes/hyphens to standard hyphen-minus
title = re.sub(r"[–—−－]", "-", title)
```

**処理内容**:
- エンダッシュ(`–`)、エムダッシュ(`—`)、マイナス記号(`−`)、全角ハイフン(`－`)などの表記揺れを、全て半角ハイフン(`-`)に統一。

---

#### 2.5. YouTube形式の処理
```python
# Extract from "Title / Artist" format (YouTube)
if " / " in title:
    title = title.split(" / ")[0]
```

**処理内容**:
- " / " 区切りの場合、最初の部分をタイトルとして使用

---

#### 2.6. 日本語『』括弧の処理
```python
# Extract from 『』 brackets (Japanese format - high priority)
if "『" in title and "』" in title:
    match = re.search(r"^[^『]*『([^』]+)』.*", title)
    if match:
        title = match.group(1)
```

**処理内容**:
- 『』括弧内の文字列をタイトルとして抽出（高優先度）

---

#### 2.7. " - " 以降の切り捨て
```python
# Truncate at " - " (often separates Artist or extra info)
if " - " in title:
    title = title.split(" - ")[0]
```

**処理内容**:
- ` - ` (スペース+ハイフン+スペース) がある場合、それ以降を全て削除。

---

#### 2.8. 全ての括弧とその中身の削除
```python
# Remove all types of brackets and their contents ((), [], 【】)
title = re.sub(r"[\(\[\【].*?[\)\]\】]", "", title)
```

**処理内容**:
- `()`, `[]`, `【】` の括弧とその中身を、内容に関わらず全て削除。

---

#### 2.9. 区切り文字の置換
```python
# Replace separator characters with space
title = re.sub(r"[\|/]", " ", title)
```

**処理内容**:
- `|` と `/` をスペースに置換

---

#### 2.10. feat./ft./featuring の削除
```python
# Remove feat./ft./featuring outside of brackets
title = re.sub(r"(feat\.|ft\.|featuring).*", "", title, flags=re.IGNORECASE)
```

**処理内容**:
- 括弧外のfeat./ft./featuring とそれ以降を全て削除

---

#### 2.11. 特殊引用符の削除
```python
# Remove special quotes
title = re.sub(r"[『』「」]", "", title)
```

**処理内容**:
- タイトルに残っている『』や「」を削除する。
- **注意**: [2.2. 特定アーティストの特別処理](#22-特定アーティストの特別処理ずっと真夜中でいいのに等) で即座にリターンされた場合は、この処理は実行されない。

---

#### 2.12. スペースの正規化
```python
# Normalize consecutive spaces to single space
title = re.sub(r"\s+", " ", title).strip()
```

---

## 3. 関数: get_lyrics() - 検索クエリ生成時のアーティスト名処理

（変更なし）

---

## 処理フロー全体図

```
playerctlから取得
    ↓
┌───────────────────────────────────────────────┐
│ clean_title() でタイトルクリーニング          │
├───────────────────────────────────────────────┤
│ 1. 特定アーティスト(「ずっと真夜中〜」等)処理 │
│    └─ 『』内抽出＆即リターン                  │
│                                               │
│ 2. Spotify形式の処理                          │
│ 3. YouTube形式の抽出                          │
│ 4. 『』括弧の抽出                             │
│ 5. キーワード括弧の削除                       │
│ 6. 区切り文字の置換                           │
│ 7. feat./ft. の削除                           │
│ 8. 特殊引用符の削除 (特定アーティスト以外)    │
│ 9. スペース正規化                             │
└───────────────────────────────────────────────┘
    ↓
(クリーンなタイトル, アーティスト名)
    ↓
┌─────────────────────────────────────┐
│ get_lyrics() で検索クエリ生成        │
├─────────────────────────────────────┤
│ 1. マッピングチェック                │
│    ├─ 該当あり → マッピング名使用   │
│    └─ 該当なし → 次の処理へ         │
│                                      │
│ 2. アーティスト名クリーニング        │
│    ├─ 絵文字除去 (U+1F000-1FFFF)    │
│    └─ 全角英数除去 (U+FF00-FFEF)    │
│                                      │
│ 3. 検索クエリ構築                    │
│    ├─ 30文字未満 →                  │
│    │   "{title} {artist}"           │
│    └─ 30文字以上or空 →              │
│        "{title}" のみ                │
└─────────────────────────────────────┘
    ↓
syncedlyricsで検索
```

---

## まとめ

### 除去される文字・パターン一覧

#### clean_title() で除去
1. `feat.` / `ft.` / `featuring` とその後続文字
2. `()`, `[]`, `【】` の括弧とその中身（**内容に関わらず全て削除**。ただし『』は抽出対象のため、この段階では除去されない）
3. 区切り文字: `|` `/` （スペースに置換）
4. 連続スペース（単一スペースに正規化）

#### get_lyrics() で除去
1. 絵文字: U+1F000-U+1FFFF
2. 全角英数字: U+FF00-U+FFEF

### 使用される検索クエリ形式

1. **マッピング該当時**: `"{title} {mapped_artist}"`
2. **通常時（アーティスト名30文字未満）**: `"{title} {clean_artist}"`
3. **アーティスト名長すぎor空**: `"{title}"` のみ