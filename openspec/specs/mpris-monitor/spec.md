# Capability: MPRIS Monitor

## Purpose
MPRISインターフェースを介してメディアプレーヤーの状態を監視し、再生位置の管理とイベントの通知を行う。

## Requirements

### Requirement: Player Detection
再生中のメディアプレーヤーを優先順位に従って検出 **SHALL** しなければならない。

#### Process Flow
```mermaid
flowchart TD
    Start[プレイヤー検出開始] --> GetAvailable[利用可能なプレイヤー取得]
    GetAvailable --> CheckPriority{優先順位リストをループ}
    CheckPriority --> |次の優先順位| MatchPlayer{プレイヤー名が一致?}
    MatchPlayer --> |No| CheckPriority
    MatchPlayer --> |Yes| CheckStatus{Playing または Paused?}
    CheckStatus --> |No| CheckPriority
    CheckStatus --> |Yes| SelectPlayer[プレイヤーを選択]
    SelectPlayer --> End[選択完了]
    CheckPriority --> |リスト終了| NoPlayer[プレイヤーなし]
```

#### Scenario: Priority matching
- **WHEN** 「brave」と「spotify」の両方が起動している
- **THEN** 「brave」が優先的に選択される

#### Scenario: Priority Re-check
- **WHEN** デーモンモードで動作している
- **THEN** 5秒ごとに、現在よりも優先順位の高いプレイヤーが再生を開始していないか確認しなければならない。
- **AND** より高い優先順位のプレイヤーが見つかった場合、即座に接続先を切り替えなければならない。

#### Process Flow
```mermaid
sequenceDiagram
    participant Daemon as デーモンループ
    participant Monitor as MPRISPlayerMonitor
    participant MPRIS as MPRISプレイヤー

    loop 5秒ごと
        Daemon->>Monitor: 優先順位チェック要求
        Monitor->>Monitor: 現在のプレイヤー優先順位を確認
        Monitor->>MPRIS: 利用可能なプレイヤー取得
        MPRIS-->>Monitor: プレイヤーリスト

        loop より高い優先順位
            Monitor->>MPRIS: プレイヤー状態確認
            MPRIS-->>Monitor: PlaybackStatus
            alt Playing または Paused
                Monitor->>Monitor: プレイヤー切り替え
                Monitor->>Monitor: トラック状態リセット
            end
        end
    end
```

### Requirement: Position Interpolation
MPRISへの負荷を抑えるため、再生位置を補完 **SHALL** しなければならない。

#### Process Flow
```mermaid
sequenceDiagram
    participant Daemon as デーモンループ
    participant Interpolator as PositionInterpolator
    participant MPRIS as MPRISプレイヤー

    Note over Daemon: 50ms間隔で実行

    Daemon->>Interpolator: 同期が必要か確認
    alt 5秒経過または初回
        Interpolator->>MPRIS: 位置・状態・レート取得
        MPRIS-->>Interpolator: Position, Status, Rate
        Interpolator->>Interpolator: スナップショット保存
    end

    Daemon->>Interpolator: 補完位置を取得
    Interpolator->>Interpolator: 経過時間 = 現在時刻 - スナップショット時刻
    Interpolator->>Interpolator: 補完位置 = スナップショット位置 + (経過時間 × レート)
    Interpolator-->>Daemon: 補完された再生位置
```

#### Scenario: Smooth interpolation
- **WHEN** MPRISとの同期が5秒間隔である
- **THEN** その間はシステム時刻の変化に基づき再生位置をミリ秒単位で更新する

### Requirement: Track Change Detection
再生中の楽曲が変更されたことを正確に検知し、メタデータを更新しなければならない (**MUST**)。

#### Process Flow
```mermaid
flowchart TD
    Start[MPRIS同期タイミング] --> GetState[メタデータ取得]
    GetState --> CheckTrackID{trackid が存在?}

    CheckTrackID --> |Yes| CompareID{前回のtrackidと異なる?}
    CompareID --> |Yes| TrackChanged[楽曲変更を検知]
    CompareID --> |No| NoChange[変更なし]

    CheckTrackID --> |No| CompareMetadata{title または artist が異なる?}
    CompareMetadata --> |Yes| TrackChanged
    CompareMetadata --> |No| NoChange

    TrackChanged --> UpdateMetadata[内部メタデータ更新]
    UpdateMetadata --> GenerateCacheKey[キャッシュキー生成]
    GenerateCacheKey --> FetchLyrics[歌詞取得/検索]
    FetchLyrics --> ParseLyrics[歌詞をパース]
    ParseLyrics --> End[処理完了]

    NoChange --> End
```

#### Scenario: Sync Interval
- **WHEN** デーモンモードで動作している
- **THEN** 5秒ごとのMPRIS同期のタイミングで楽曲変更を確認しなければならない。

#### Scenario: Detection Logic
- **WHEN** 楽曲変更を確認する
- **THEN** 以下の優先順位で変更を判定しなければならない:
    1. `mpris:trackid` が前回のIDと異なる場合
    2. トラックIDが無い場合、`xesam:title` または `xesam:artist` が前回の値と異なる場合

#### Scenario: Action on Change
- **WHEN** 楽曲の変更が検知される
- **THEN** 直ちに内部のメタデータ（タイトル、アーティスト）を更新しなければならない。
- **AND** 新しいメタデータに基づいて歌詞の再取得（キャッシュ確認または新規検索）を実行しなければならない。

### Requirement: Daemon Execution
継続的な監視を行い、結果を外部ファイルへ出力 **MUST** しなければならない。

#### Process Flow
```mermaid
sequenceDiagram
    participant Daemon as LyricsDaemon
    participant Monitor as MPRISPlayerMonitor
    participant Interpolator as PositionInterpolator
    participant TrackMgr as TrackStateManager
    participant FS as ファイルシステム

    Note over Daemon: 50ms間隔でループ

    loop 毎イテレーション
        Daemon->>Monitor: プレイヤー接続確認
        alt プレイヤー未接続
            Monitor->>Monitor: アクティブプレイヤー検索
        end

        Daemon->>Interpolator: 同期が必要か確認
        alt 同期が必要
            Interpolator->>Monitor: MPRIS状態取得
            Monitor-->>Interpolator: Position, Status, Rate, Metadata
            Interpolator->>Interpolator: スナップショット更新

            Daemon->>TrackMgr: 楽曲変更チェック
            alt 楽曲変更あり
                TrackMgr->>TrackMgr: メタデータ更新
                TrackMgr->>TrackMgr: 歌詞取得/検索
            end
        end

        Daemon->>Interpolator: 補完位置取得
        Interpolator-->>Daemon: 現在位置

        Daemon->>Daemon: JSON出力生成
        Daemon->>FS: 一時ファイル書き込み
        Daemon->>FS: アトミックリネーム
        Note over FS: /tmp/lyrics-daemon.json
    end
```

#### Scenario: Atomic file update
- **WHEN** デーモンが新しい歌詞情報を生成する
- **THEN** `/tmp/lyrics-daemon.json` へアトミックに書き込みを行う
