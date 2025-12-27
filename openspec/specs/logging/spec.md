# Capability: Logging and Debugging

## Purpose
システムの稼働状況、検索クエリ、エラー発生時の詳細を記録し、トラブルシューティングを容易にする。

## Requirements

### Requirement: Log Destinations
実行モードに応じて適切な場所へログを出力しなければならない (**MUST**)。

#### Process Flow
```mermaid
flowchart TD
    A[プログラム起動] --> B{実行モード判定}
    B -->|--daemon フラグあり| C[デーモンモード]
    B -->|--daemon フラグなし| D[インタラクティブモード]

    C --> E[stdout/stderr を<br>/tmp/lyrics-daemon.log へリダイレクト]
    D --> F[stderr へログ出力<br>stdoutは結果のみ]

    E --> G[ログファイルに集約]
    F --> H[ターミナルに出力]
```

#### Scenario: Daemon Logging
- **WHEN** デーモンモードで実行されている
- **THEN** 標準出力および標準エラー出力の両方を `/tmp/lyrics-daemon.log` に集約して記録しなければならない。

#### Scenario: Interactive Debugging
- **WHEN** ターミナルから直接実行されている
- **THEN** デバッグ情報やエラー情報を標準エラー出力 (`stderr`) に出力し、標準出力 (`stdout`) の結果を汚さないようにしなければならない。

### Requirement: Logged Events
以下の重要なイベントを適切なログレベルとプレフィックスで記録しなければならない (**MUST**)。

#### Process Flow
```mermaid
sequenceDiagram
    participant System as システム
    participant Logger as ロガー
    participant Output as 出力先

    Note over System,Output: デーモン起動/停止
    System->>Logger: [INFO] デーモン起動/停止<br>(PID情報含む)
    Logger->>Output: stderr/ログファイルへ出力

    Note over System,Output: プレイヤー状態変化
    System->>Logger: [INFO] Playing/Paused切替<br>優先順位によるプレイヤー切替
    Logger->>Output: stderr/ログファイルへ出力

    Note over System,Output: 歌詞検索 (デーモンモードのみ)
    System->>Logger: [Lyrics Search] クエリ詳細<br>(クエリ文字列、元タイトル、元アーティスト)
    Logger->>Output: stdout/ログファイルへ出力

    Note over System,Output: デバッグ情報
    System->>Logger: [DEBUG] MPRISプレイヤーリスト<br>プレイヤーIDマッチング<br>接続エラー
    Logger->>Output: stderr/ログファイルへ出力

    Note over System,Output: エラー
    System->>Logger: [ERROR] 未処理例外<br>ファイル書き込み失敗<br>(スタックトレース含む)
    Logger->>Output: stderr/ログファイルへ出力
```

#### Scenario: Key events
- **WHEN** システムが動作する
- **THEN** 以下のイベントカテゴリに対応するプレフィックスを使用して記録しなければならない:
    - `[INFO]`:
        - デーモンの起動・停止（PID情報含む）
        - プレイヤーの再生状態変化（Playing ↔ Paused）
        - 優先順位によるプレイヤーの切り替え
    - `[Lyrics Search]`:
        - 検索実行時のクエリ詳細（クエリ文字列、元タイトル、元アーティスト）
        - ※デーモンモード実行時のみ出力
    - `[ERROR]`:
        - 未処理の例外（スタックトレース含む）
        - ファイル書き込み（PIDファイル、JSON出力）の失敗
    - `[DEBUG]`:
        - 利用可能なMPRISプレイヤーのリスト列挙
        - プレイヤーIDのマッチングプロセス
        - 個別のプレイヤー接続エラー

### Requirement: Log Format
ログメッセージは識別しやすいプレフィックスを含まなければならない (**MUST**)。

#### Process Flow
```mermaid
flowchart TD
    A[ログイベント発生] --> B{イベント種別判定}

    B -->|情報| C["[INFO] プレフィックス付与"]
    B -->|歌詞検索| D["[Lyrics Search] プレフィックス付与"]
    B -->|デバッグ| E["[DEBUG] プレフィックス付与"]
    B -->|エラー| F["[ERROR] プレフィックス付与"]

    C --> G[メッセージ本文追加]
    D --> G
    E --> G
    F --> G

    G --> H{デーモンモード?}
    H -->|Yes| I[ログファイルへ出力]
    H -->|No| J[stderr へ出力]
```

#### Scenario: Consistent Prefixing
- **WHEN** ログが出力される
- **THEN** メッセージの冒頭に `[INFO]`, `[ERROR]`, `[DEBUG]`, `[Lyrics Search]` のいずれかを付与し、カテゴリを明確に区別しなければならない。
