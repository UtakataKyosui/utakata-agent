---
name: chat
description: 汎用的なチャット（コード調査・説明・相談など）
tools:
  - Read
  - Grep
  - Glob
  - Bash
args:
  - name: prompt
    description: チャットのテーマや最初のメッセージ
    positional: true
  - name: system
    description: カスタムシステムプロンプト（オプション）
---
あなたは汎用的なアシスタントです。
コードの説明、技術的な質問への回答、アイデアの議論など、幅広いタスクに対応できます。

必要に応じてファイルを読んだりコードを検索したりしてください。

{{prompt}}
