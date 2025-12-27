# Capability: Lyrics Output

## Purpose
取得した歌詞情報を、様々なデスクトップツール（Eww, Waybar, CLI）が解釈可能な形式で出力する。

## Requirements

### Requirement: Eww Output Format
Ewwなどのウィジェットで使用するためのJSON形式を出力 **SHALL** しなければならない。

#### Process Flow
```mermaid
flowchart TD
    Start[output_json 関数開始] --> CheckLyrics{歌詞が存在するか?}
    CheckLyrics -->|No| ReturnNoLyrics[status: no_lyrics を返す]
    CheckLyrics -->|Yes| CheckSynced{同期歌詞か?}

    CheckSynced -->|Yes| FindCurrent[find_current_line で現在行を特定]
    FindCurrent --> CalcRange[現在行の前後3行を計算<br/>start = current - 3<br/>end = current + 4]
    CalcRange --> BuildLines[各行のタイムスタンプを除去し<br/>current フラグを付与]
    BuildLines --> ReturnSynced[status: ok と lines 配列を返す]

    CheckSynced -->|No| TakeFirst10[最初の10行を取得]
    TakeFirst10 --> ReturnUnsynced[status: ok と lines 配列を返す<br/>current: false]
```

#### Scenario: Current and surrounding lines
- **WHEN** 同期された歌詞を表示する
- **THEN** 現在の行を中心に前後数行を含むJSONを出力する

### Requirement: Waybar Output Format
Waybarのカスタムモジュール用JSON形式を出力 **SHALL** しなければならない。

#### Process Flow
```mermaid
flowchart TD
    Start[output_waybar 関数開始] --> CheckLyrics{歌詞が存在するか?}
    CheckLyrics -->|No| ReturnHidden[text: 空文字<br/>class: hidden<br/>tooltip: No lyrics found]

    CheckLyrics -->|Yes| CheckSynced{同期歌詞か?}

    CheckSynced -->|Yes| FindCurrent[find_current_line で現在行を特定]
    FindCurrent --> CheckCurrentValid{current_idx >= 0?}
    CheckCurrentValid -->|Yes| CalcRange[現在行の前後2行を計算<br/>start = current - 2<br/>end = current + 3]
    CalcRange --> BuildTooltip[各行を処理:<br/>- 空行は ♪ に変換<br/>- 現在行に ▶ プレフィックス<br/>- 他の行に空白プレフィックス]
    BuildTooltip --> SetCurrent[current_lyric に現在行を設定]
    SetCurrent --> EscapeHTML[text と tooltip を<br/>html.escape でエスケープ]

    CheckSynced -->|No| TakeFirst20[最初の20行を取得]
    TakeFirst20 --> CheckMore{20行以上?}
    CheckMore -->|Yes| AddEllipsis[... 以下省略 を追加]
    CheckMore -->|No| NoEllipsis[そのまま]
    AddEllipsis --> NoCurrentUnsync[current_lyric は空]
    NoEllipsis --> NoCurrentUnsync
    NoCurrentUnsync --> EscapeHTML

    CheckCurrentValid -->|No| NoCurrentUnsync

    EscapeHTML --> Return[JSON を返す:<br/>text: 󰎆 + current_lyric<br/>class: visible<br/>tooltip: エスケープ済み歌詞]
```

#### Scenario: Escaped tooltip
- **WHEN** 歌詞をツールチップに表示する
- **THEN** HTML特殊文字をエスケープしたJSONを出力する
