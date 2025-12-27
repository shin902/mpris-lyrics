# Capability: Lyrics Fetching

## Purpose
メディアプレーヤーから取得した情報を検索エンジンに適した形式に変換し、同期された歌詞を取得・キャッシュする。

## Requirements

### Requirement: Title Cleaning
playerctlから取得した生のタイトル文字列から、不要な要素（[MV]、(feat. ...)、YouTubeの「 / 」区切りなど）を除去してクリーンな曲名を抽出 **SHALL** しなければならない。

#### Process Flow
```mermaid
flowchart TD
    Start[タイトル文字列を受け取る] --> CheckZutomayo{アーティストが<br/>ずっと真夜中でいいのに。?}
    CheckZutomayo -->|Yes| HasKagikakko{タイトルに『』がある?}
    HasKagikakko -->|Yes| ExtractKagikakko[『』内を抽出]
    ExtractKagikakko --> RemoveParens[半角括弧を除去]
    RemoveParens --> End[クリーニング完了]

    HasKagikakko -->|No| CheckSpotify
    CheckZutomayo -->|No| CheckSpotify{プレイヤーがSpotify?}

    CheckSpotify -->|Yes| RemoveFeat[feat./ft.のみ除去]
    RemoveFeat --> End

    CheckSpotify -->|No| GeneralFlow[汎用クリーニング処理]
    GeneralFlow --> CheckGeneralKagikakko{『』がある?}
    CheckGeneralKagikakko -->|Yes| ExtractGeneralKagikakko[『』内を抽出]
    CheckGeneralKagikakko -->|No| CheckSlash

    ExtractGeneralKagikakko --> CheckSlash{スラッシュ区切りがある?}
    CheckSlash -->|Yes| TruncateSlash[スラッシュより前を抽出]
    CheckSlash -->|No| RemoveBrackets
    TruncateSlash --> RemoveBrackets[全ての括弧と中身を削除]
    RemoveBrackets --> NormalizeSpaces[連続スペースを正規化]
    NormalizeSpaces --> End
```

#### Scenario: Prioritized extraction for specific artists
- **WHEN** アーティストが「ずっと真夜中でいいのに。 ZUTOMAYO」であり、タイトルに「『...』」が含まれる場合
- **THEN** 「『』」内のみを抽出し、さらに半角括弧を除去した時点でクリーニングを完了（早期リターン）しなければならない。

#### Scenario: Limited cleaning for Spotify
- **WHEN** メディアプレーヤーが「Spotify」である場合
- **THEN** `feat.` や `ft.` の除去のみを行い、他の汎用的なクリーニング処理（スラッシュ分割等）はスキップして終了しなければならない。

#### Scenario: General Flow - Extract from double brackets
- **WHEN** 上記の優先ルールに該当せず、タイトルに「『』」が含まれる場合
- **THEN** 「『』」内の中身を抽出する。

#### Scenario: General Flow - Truncate at slash separator
- **WHEN** タイトルに「 / 」（スペース+スラッシュ+スペース）が含まれる
- **THEN** 最初の区切り文字「 / 」より前の部分のみを抽出する。

#### Scenario: General Flow - Remove brackets and contents
- **WHEN** タイトルに「Song Title (Any Content) [Meta] 【補足】」のような括弧が含まれる
- **THEN** 半角・全角問わず、括弧とその中身を無条件に全て削除する。


### Requirement: Artist Mapping and Cleaning
検索精度向上のため、アーティスト名を正規化 **SHALL** しなければならない。

#### Process Flow
```mermaid
flowchart TD
    Start[アーティスト名を受け取る] --> CheckMapping{マッピング辞書に<br/>登録されている?}
    CheckMapping -->|Yes| UseMapping[マッピング後の名前を使用]
    UseMapping --> BuildQuery[検索クエリを構築]

    CheckMapping -->|No| CleanArtist[アーティスト名をクリーニング]
    CleanArtist --> RemoveEmoji[絵文字を除去<br/>U+1F000-U+1FFFF]
    RemoveEmoji --> RemoveFullWidth[全角英数字を除去<br/>U+FF00-U+FFEF]
    RemoveFullWidth --> CheckLength{クリーン名の<br/>長さ < 30?}

    CheckLength -->|Yes| UseCleanName[クリーン名を使用]
    CheckLength -->|No| UseTitleOnly[タイトルのみで検索]

    UseCleanName --> BuildQuery
    UseTitleOnly --> BuildQuery
    BuildQuery --> End[検索クエリ完成]
```

#### Scenario: Use predefined mapping
- **WHEN** アーティスト名が「ずっと真夜中でいいのに。 ZUTOMAYO」である
- **THEN** マッピングに基づき「ずっと真夜中でいいのに。」として検索される

#### Scenario: Remove emojis and full-width chars
- **WHEN** アーティスト名に絵文字や全角英数字が含まれる
- **THEN** それらを除去したクリーンな名前で検索される

### Requirement: Lyrics Caching
取得した歌詞はキャッシュ **MUST** し、不要なAPIリクエストを防止しなければならない。

#### Process Flow
```mermaid
flowchart TD
    Start[キャッシュキー生成<br/>MD5 artist+title] --> CheckCache{キャッシュファイル<br/>が存在する?}

    CheckCache -->|No| FetchLyrics[syncedlyrics で検索]
    FetchLyrics --> CheckResult{歌詞が<br/>見つかった?}

    CheckResult -->|Yes| SaveLyrics[歌詞をキャッシュに保存]
    CheckResult -->|No| SaveEmpty[空ファイルを保存]

    SaveLyrics --> SaveMeta[メタデータを保存<br/>title, artist, cache_key]
    SaveEmpty --> SaveMeta
    SaveMeta --> ReturnLyrics[歌詞を返す]

    CheckCache -->|Yes| CheckMeta{メタデータ<br/>ファイルが存在する?}
    CheckMeta -->|No| UseCached[キャッシュを信頼して使用]
    UseCached --> ReturnLyrics

    CheckMeta -->|Yes| ReadMeta[メタデータを読み込み]
    ReadMeta --> ValidateMeta{title と artist<br/>が一致する?}

    ValidateMeta -->|Yes| UseCached
    ValidateMeta -->|No| DeleteStale[古いキャッシュを削除]
    DeleteStale --> FetchLyrics

    ReturnLyrics --> End[完了]
```

#### Scenario: Valid cache hit
- **WHEN** キャッシュファイルが存在し、メタデータ（タイトル、アーティスト）が一致する
- **THEN** キャッシュされた歌詞を即座に返す

#### Scenario: Stale cache invalidation
- **WHEN** キャッシュはあるがメタデータが一致しない
- **THEN** キャッシュを削除して再検索を行う
