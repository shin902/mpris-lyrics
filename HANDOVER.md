# Lyrics Script Migration Handover

このドキュメントは、`dotfiles-linux/scripts/lyrics` を独立したリポジトリ `mpris-lyrics` へ分離・移行する作業の引継ぎ書です。

## 1. プロジェクト概要
Linux用歌詞取得ツール（MPRIS対応、syncedlyrics使用）を、dotfilesから切り出して独立管理するために分離しました。

- **旧場所**: `~/ghq/github.com/shin902/dotfiles-linux/scripts/lyrics`
- **新場所**: `~/ghq/github.com/shin902/mpris-lyrics`

## 2. 現在のステータス

### 完了した作業
- [x] 新しいリポジトリディレクトリへのファイル移動 (`universal_lyrics.py`, `start-lyrics-daemon.sh` 等)
- [x] `dotfiles-linux` 側に関連ファイルの削除
- [x] `dotfiles-linux/scripts/launch-lyrics.sh` (ラッパースクリプト) の作成
- [x] Systemd (`lyrics-daemon.service`) と Hyprland (`autostart.conf`) の設定をラッパー経由に変更
- [x] 新リポジトリ側の `start-lyrics-daemon.sh` のパス修正 (`$LYRICS_DIR` -> `$SCRIPT_DIR`)
- [x] 新リポジトリ側に `.mise.toml` を配置 (`python = "3.11"`, `uv = "latest"`)
- [x] `mise trust` および `uv sync` による環境構築完了
- [x] Git初期化 (`git init`) と初回コミット完了
- [x] デバッグログの追加（キャッシュキー生成、ヒット確認）

### 進行中の作業・問題点
- **デーモンでの検索ハング**: デーモンモードで実行すると `syncedlyrics` の検索処理が開始されたまま完了せず、JSON出力が更新されない現象が発生中。
- **キャッシュキーの不一致**: 手動実行とデーモン実行でキャッシュキー生成ロジック（`trackid` 依存）が異なり、手動取得したキャッシュがデーモンでヒットしない。
    - 手動実行: `artist + title` ベース（成功）
    - デーモン: `trackid` ベース（検索へ行きハング）

## 3. 次のアクション

1.  **キャッシュキー生成ロジックの変更**:
    - `universal_lyrics.py` を修正し、`trackid` 依存を排除して常に `artist + title` でキャッシュキーを生成するように統一する。
    - これにより、手動実行で生成したキャッシュをデーモンが読み込めるようにし、検索処理をバイパスさせる。

2.  **動作確認**:
    - 修正後、手動で歌詞を取得（キャッシュ生成）。
    - デーモンを再起動し、キャッシュがヒットして正常にJSONが出力されるか確認。

3.  **dotfiles側のクリーンアップ**:
    - `dotfiles-linux` リポジトリの変更をコミットする。

## 4. 関連ファイル
- **本体**: `universal_lyrics.py` (メインロジック、クリーニング処理含む)
- **起動**: `start-lyrics-daemon.sh` (デーモン起動用)
- **ドキュメント**: `docs/lyrics-cleaning-spec.md` (クリーニング仕様書)