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

### 進行中の作業・問題点
- **`mise` の信頼確認**: 新しいディレクトリ (`mpris-lyrics`) に `.mise.toml` を置いたため、`mise` が実行前に信頼確認（Trust? y/n）を求めていますが、非対話モードで実行したため停止しました。
- **依存関係の未解決**: `uv sync` がまだ完了していません（`mise` のエラーのため）。
- **デーモン未起動**: 上記理由により、まだ歌詞取得デーモンは起動していません。

## 3. 次のアクション（新セッションでの指示）

新しいGeminiセッションを `~/ghq/github.com/shin902/mpris-lyrics` で起動し、以下の手順を実行してください。

1.  **miseの信頼設定**:
    ```bash
    mise trust
    ```
    を実行して、設定ファイルを信頼してください。

2.  **依存関係のインストール**:
    ```bash
    mise install
    uv sync
    ```
    を実行して、仮想環境 (`.venv`) を構築してください。

3.  **デーモンの起動確認**:
    ```bash
    ./start-lyrics-daemon.sh
    # または dotfiles側から
    ~/ghq/github.com/shin902/dotfiles-linux/scripts/launch-lyrics.sh
    ```
    を実行し、`ps aux | grep universal_lyrics` でプロセスが生きているか確認してください。

4.  **Git初期化とコミット**:
    ```bash
    git init
    git add .
    git commit -m "feat: initial commit of mpris-lyrics fetcher"
    ```
    を行い、GitHubへプッシュしてください。

5.  **dotfiles側のクリーンアップ**:
    元の `dotfiles-linux` リポジトリに戻り、変更（設定ファイルの書き換えとラッパースクリプトの追加）をコミットしてください。

## 4. 関連ファイル
- **本体**: `universal_lyrics.py` (メインロジック、クリーニング処理含む)
- **起動**: `start-lyrics-daemon.sh` (デーモン起動用)
- **ドキュメント**: `docs/lyrics-cleaning-spec.md` (クリーニング仕様書)
