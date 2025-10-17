import yt_dlp
import requests
import re
import json
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

def extract_video_id(url):
    match = re.search(r"(?:v=|youtu\.be/)([\w-]{11})", url)
    return match.group(1) if match else None


def get_subtitle_text(video_url):
    """yt-dlp로 자막 데이터 가져오기 + 텍스트 추출"""
    ydl_opts = {
        "skip_download": True,
        "writesubtitles": True,
        "writeautomaticsub": True,
        "quiet": True,
        # ↓ 자막 언어 우선순위: 한국어 → 자동생성 한국어 → 영어
        "subtitleslangs": ["ko", "ko-kr", "a.ko", "a.ko-kr", "en"],
        "subtitlesformat": "srv3"
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(video_url, download=False)
        subs = info.get("subtitles") or info.get("automatic_captions")
        if not subs:
            raise ValueError("자막 트랙이 없습니다.")

        # 💡 'ko'로 시작하는 트랙 먼저 탐색
        for lang, tracks in subs.items():
            if not tracks:
                continue
            if lang.startswith("ko"):  # 한국어 자막이면 바로 사용
                sub_url = tracks[0]["url"]
                resp = requests.get(sub_url)
                if resp.status_code == 200:
                    import json
                    data = json.loads(resp.text)
                    text = " ".join(
                        seg["utf8"]
                        for ev in data.get("events", [])
                        for seg in ev.get("segs", [])
                        if "utf8" in seg
                    )
                    return text

        # 한국어 없으면 영어 등 다른 언어라도 반환
        for lang, tracks in subs.items():
            if tracks and "url" in tracks[0]:
                sub_url = tracks[0]["url"]
                resp = requests.get(sub_url)
                if resp.status_code == 200:
                    return resp.text
        raise ValueError("자막 데이터를 가져올 수 없습니다.")


@app.route('/')
def home():
    return render_template('index.html')

@app.route('/api/transcript', methods=['POST'])
def get_transcript():
    data = request.get_json()
    url = data.get('url', '')
    video_id = extract_video_id(url)

    if not video_id:
        return jsonify({'ok': False, 'error': '유효한 유튜브 URL이 아닙니다.'}), 400

    try:
        text = get_subtitle_text(url)
        return jsonify({'ok': True, 'video_id': video_id, 'text': text})
    except Exception as e:
        return jsonify({'ok': False, 'error': f'자막을 가져오는 중 오류 발생: {e}'}), 400


if __name__ == '__main__':
    app.run(debug=True)
