# Capability: CLI Interface

## Purpose
ツールの動作モード（デーモン/単発取得）や出力形式を制御するためのユーザーインターフェースを定義する。

## Requirements

### Requirement: Command Line Arguments
ユーザーはコマンドライン引数を通じて挙動を制御可能でなければならない (**MUST**)。

#### Process Flow
```mermaid
flowchart TD
    Start([コマンド実行]) --> ParseArgs[引数解析]
    ParseArgs --> CheckTarget{--target指定?}
    CheckTarget -->|Yes| SetTarget[対象プレイヤー設定]
    CheckTarget -->|No| DefaultTarget[全プレイヤー対象]
    SetTarget --> CheckFormat{--format指定?}
    DefaultTarget --> CheckFormat
    CheckFormat -->|json| SetJSON[JSON形式]
    CheckFormat -->|waybar| SetWaybar[Waybar形式]
    CheckFormat -->|text| SetText[Text形式]
    CheckFormat -->|raw| SetRaw[Raw形式]
    CheckFormat -->|未指定| SetJSON
    SetJSON --> CheckDaemon{--daemon指定?}
    SetWaybar --> CheckDaemon
    SetText --> CheckDaemon
    SetRaw --> CheckDaemon
    CheckDaemon -->|Yes| DaemonMode[デーモンモード]
    CheckDaemon -->|No| OneShotMode[単発モード]
    DaemonMode --> Execute[実行]
    OneShotMode --> Execute
```

#### Scenario: Supported arguments
- **WHEN** コマンドライン引数が提供される
- **THEN** 以下の引数を受け入れなければならない:
    - `--target`: 対象とする特定のプレイヤー名（部分一致）
    - `--format`: 出力形式 (`json`, `waybar`, `text`, `raw`)
    - `--daemon`: 高リフレッシュレートのデーモンモードで実行

### Requirement: Output Formats
指定された形式に従って標準出力へ結果を書き出さなければならない (**MUST**)。

#### Process Flow
```mermaid
flowchart TD
    Start([歌詞データ取得]) --> CheckFormat{出力形式}
    CheckFormat -->|json| BuildJSON[JSON構造構築]
    CheckFormat -->|waybar| BuildWaybar[Waybarカスタムモジュール構築]
    CheckFormat -->|text| BuildText[プレーンテキスト構築]
    CheckFormat -->|raw| GetRaw[生LRCファイル取得]

    BuildJSON --> JSONStructure[現在行+前後行を含む]
    JSONStructure --> OutputJSON[標準出力]

    BuildWaybar --> WaybarStructure[text, tooltip, class]
    WaybarStructure --> OutputWaybar[標準出力]

    BuildText --> TextFormat[シンプルなテキスト]
    TextFormat --> OutputText[標準出力]

    GetRaw --> OutputRaw[LRC内容をそのまま出力]

    OutputJSON --> End([終了])
    OutputWaybar --> End
    OutputText --> End
    OutputRaw --> End
```

#### Scenario: JSON Format (Default)
- **WHEN** `--format json` が指定される
- **THEN** 現在の歌詞行とその前後を含むJSON構造を出力しなければならない。

#### Scenario: Waybar Format
- **WHEN** `--format waybar` が指定される
- **THEN** Waybarのカスタムモジュール用JSON（`text`, `tooltip`, `class`）を出力しなければならない。

#### Scenario: Raw Format
- **WHEN** `--format raw` が指定される
- **THEN** 取得されたLRCファイルの内容をそのまま出力しなければならない。

### Requirement: Execution Modes
単発実行モードとデーモンモードの2つのモードをサポートしなければならない (**MUST**)。

#### Process Flow
```mermaid
sequenceDiagram
    participant User as ユーザー
    participant CLI as CLIプログラム
    participant MPRIS as MPRISプレイヤー
    participant LyricsAPI as 歌詞API
    participant FS as ファイルシステム

    alt One-shot Mode (--daemon なし)
        User->>CLI: コマンド実行
        CLI->>MPRIS: プレイヤー状態取得
        alt プレイヤーが見つかった
            MPRIS-->>CLI: メタデータ+再生位置
            CLI->>LyricsAPI: 歌詞検索
            alt 歌詞が見つかった
                LyricsAPI-->>CLI: 歌詞データ
                CLI->>CLI: 現在行を計算
                CLI->>User: 結果を標準出力
            else 歌詞が見つからない
                LyricsAPI-->>CLI: 404
                CLI->>User: 空の結果を出力
            end
        else プレイヤーが見つからない
            MPRIS-->>CLI: 空
            CLI->>User: 空の結果を出力
        end
        CLI->>User: 終了コード 0 で終了
    else Daemon Mode (--daemon 指定)
        User->>CLI: コマンド実行（デーモン）
        loop 20Hz (50ms間隔)
            CLI->>MPRIS: プレイヤー状態取得
            MPRIS-->>CLI: メタデータ+再生位置
            CLI->>CLI: 前回と異なるトラック?
            alt トラックが変わった
                CLI->>LyricsAPI: 新しい歌詞を取得
                LyricsAPI-->>CLI: 歌詞データ
            end
            CLI->>CLI: 現在行を計算
            CLI->>FS: /tmp/lyrics-daemon.json へアトミックに書き込み
        end
    end
```

#### Scenario: One-shot Mode
- **WHEN** `--daemon` が指定されない
- **THEN** 現在の状態を一度だけ取得して終了しなければならない。
- **AND** プレイヤーが見つからない、または歌詞が見つからない場合でも終了コード `0` で正常終了しなければならない。

#### Scenario: Daemon Mode
- **WHEN** `--daemon` が指定される
- **THEN** 20Hz (50ms間隔) で再生位置を更新し続けなければならない。
- **AND** 結果を `/tmp/lyrics-daemon.json` へアトミックに書き込み続けなければならない。
