# Capability: MPRIS Monitor

## Purpose
MPRISインターフェースを介してメディアプレーヤーの状態を監視し、再生位置の管理とイベントの通知を行う。

## Requirements

### Requirement: Player Detection
再生中のメディアプレーヤーを優先順位に従って検出 **SHALL** しなければならない。

#### Scenario: Priority matching
- **WHEN** 「brave」と「spotify」の両方が起動している
- **THEN** 「brave」が優先的に選択される

### Requirement: Position Interpolation
MPRISへの負荷を抑えるため、再生位置を補完 **SHALL** しなければならない。

#### Scenario: Smooth interpolation
- **WHEN** MPRISとの同期が5秒間隔である
- **THEN** その間はシステム時刻の変化に基づき再生位置をミリ秒単位で更新する

### Requirement: Daemon Execution
継続的な監視を行い、結果を外部ファイルへ出力 **MUST** しなければならない。

#### Scenario: Atomic file update
- **WHEN** デーモンが新しい歌詞情報を生成する
- **THEN** `/tmp/lyrics-daemon.json` へアトミックに書き込みを行う
