# Project Context

## Purpose
MPRIS (Media Player Remote Interfacing Specification) を介してメディアプレーヤーから再生情報を取得し、同期された歌詞（LRC等）を取得・表示するツール。デスクトップ環境（Waybar, Eww等）への統合を主な目的とする。

## Tech Stack
- **言語**: Python 3.11+
- **パッケージ管理**: uv
- **主要ライブラリ**:
    - `syncedlyrics`: 歌詞の検索とダウンロード
    - `pympris`, `dbus-python`: MPRIS経由のメディアプレーヤー制御
    - `PyGObject`: GLib/DBusイベントループ用（ただし現在はポーリングベースのデーモン実装）

## Project Conventions

### Code Style
- **言語**: 日本語（コメント、ドキュメント）/ 英語（コード、変数名）
- **型ヒント**: Python 3.11 の型ヒントを積極的に活用。
- **ドキュメント**: ロジックの詳細は `docs/` 配下に Markdown で記述し、OpenSpec と同期させる。

### Architecture Patterns
- **デーモン/CLIのハイブリッド**: 同じスクリプトが引数によって1回限りの取得と、継続的な監視デーモンの両方として動作。
- **位置補完 (Interpolation)**: MPRIS への問い合わせ負荷を下げるため、5秒ごとの同期と、その間の時間はシステム時刻に基づいた計算による位置補完を行う。
- **クリーニングファースト**: 検索精度の向上のため、プレーヤーから取得したタイトルとアーティスト名を厳格にクリーニングする。

### Testing Strategy
- 現在、明示的なテストフレームワークは導入されていないが、今後は `pytest` 等の導入を検討。

### Git Workflow
- OpenSpec に基づく仕様駆動開発。
- コミットメッセージは「Why」を重視。

## Domain Context
- **歌詞クリーニング**: 日本語の曲名に特化した処理（『』からの抽出、特定のアーティスト向けの例外処理など）が含まれている。詳細は `docs/lyrics-cleaning-spec.md` を参照。
- **キャッシュ**: `/tmp/lyrics_cache` に LRC ファイルとメタデータを保存し、不要な再検索を防止。

## Important Constraints
- デーモンモードは `/tmp/lyrics-daemon.json` へのアトミックな書き込みによって結果を公開する。

## External Dependencies
- `playerctl`: CLI経由での情報取得に使用。
- MPRIS 準拠のメディアプレーヤー（Spotify, Brave 等）。