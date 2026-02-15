# ffmpeg_MultiEncoder

このリポジトリは、`ffmpeg` バイナリとプリセットをまとめたローカル用のコレクションです。
マルチエンコーダやスクリプトで `ffmpeg` を簡単に利用できるように、配布ドットや設定例を収録しています。

**構成**
- `ffmpeg/`: ビルド済みバイナリ類、ドキュメント、プリセットを格納します。
	- `ffmpeg/bin/` : 実行ファイル（配布されている場合）
	- `ffmpeg/presets/` : エンコードプリセット（例: `libvpx-1080p.ffpreset`）
	- `ffmpeg/doc/` : FFmpeg の公式ドキュメント HTML

**前提**
- Windows 環境での利用を想定しています。`ffmpeg/bin/` にある実行ファイルを PATH に追加するか、フルパスで呼び出してください。

**使い方（例）**
1. `ffmpeg/bin/ffmpeg.exe` が存在することを確認します。
2. プリセットを指定してエンコードする例:

```
ffmpeg -i input.mp4 -f ffpreset -preset ffmpeg/presets/libvpx-1080p.ffpreset output.webm
```

（注）実際のコマンドはプリセットの形式や ffmpeg のビルドオプションに依存します。

**プリセット**
- `ffmpeg/presets/` にあるファイルを参照してください。用途に合わせてコピーして編集して使えます。

**ライセンス**
- `ffmpeg/` 以下に含まれるファイルはそれぞれ元のライセンスに従います。`ffmpeg/LICENSE` を参照してください。

**連絡・貢献**
- このリポジトリは個人用のコレクションです。改善提案や問題報告は Issue または Pull Request でお願いします。
