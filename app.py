import os
import json
import logging
import urllib.parse
import requests
from flask import Flask, render_template, request, jsonify, send_from_directory
from dotenv import load_dotenv
from google import genai
from google.genai import types

# 1. 환경 변수(.env) 로드
load_dotenv()

from jinja2 import ChoiceLoader, FileSystemLoader

# 로깅 설정
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, "templates"),
    static_folder=os.path.join(BASE_DIR, "static")
)

# Vercel Serverless 번들 경로를 모두 포함하는 다중 템플릿 로더
app.jinja_loader = ChoiceLoader([
    FileSystemLoader(os.path.join(BASE_DIR, "templates")),
    FileSystemLoader(os.path.join(BASE_DIR, "api", "templates")),
    FileSystemLoader(os.path.join(os.getcwd(), "templates")),
    FileSystemLoader(os.path.join(os.getcwd(), "api", "templates")),
])

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
SERPER_API_KEY = os.getenv("SERPER_API_KEY")
PORT = int(os.getenv("PORT", 5000))

# Gemini 클라이언트 초기화
genai_client = None
if GEMINI_API_KEY and GEMINI_API_KEY != "your_gemini_api_key_here":
    try:
        genai_client = genai.Client(api_key=GEMINI_API_KEY)
    except Exception as e:
        logging.error(f"Gemini 클라이언트 초기화 실패: {e}")

# 다중 모델 자동 폴백 목록
FALLBACK_MODELS = [
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
    "gemini-flash-lite-latest",
    "gemini-3.8-flash",
    "gemini-3.5-flash",
    "gemini-2.5-pro"
]


def search_youtube_video(menu_name):
    """유튜브 요리 영상 검색 (Serper Video API 연동 및 URL 생성)"""
    encoded_query = urllib.parse.quote(f"{menu_name} 레시피 만드는법")
    direct_youtube_url = f"https://www.youtube.com/results?search_query={encoded_query}"
    
    video_info = {
        "youtube_url": direct_youtube_url,
        "title": f"{menu_name} 황금레시피 영상 검색",
        "channel": "YouTube 요리 채널",
        "thumbnail": None
    }

    if SERPER_API_KEY and SERPER_API_KEY != "your_serper_api_key_here":
        try:
            url = "https://google.serper.dev/videos"
            payload = json.dumps({"q": f"{menu_name} 요리 레시피 만드는법", "gl": "kr", "hl": "ko", "num": 1})
            headers = {"X-API-KEY": SERPER_API_KEY, "Content-Type": "application/json"}
            response = requests.post(url, headers=headers, data=payload, timeout=4)
            if response.status_code == 200:
                data = response.json()
                videos = data.get("videos", [])
                if videos and len(videos) > 0:
                    v = videos[0]
                    video_info["youtube_url"] = v.get("link", direct_youtube_url)
                    video_info["title"] = v.get("title", f"{menu_name} 영상 레시피")
                    video_info["channel"] = v.get("channel", "YouTube")
                    video_info["thumbnail"] = v.get("imageUrl")
        except Exception as e:
            logging.warning(f"유튜브 영상 검색 중 오류 (직접 링크로 대체): {e}")

    return video_info


def get_static_dir(rel_path):
    candidates = [
        app.static_folder,
        os.path.join(BASE_DIR, "api", "static"),
        os.path.join(os.getcwd(), "static"),
        os.path.join(os.getcwd(), "api", "static"),
    ]
    for folder in candidates:
        if folder and os.path.exists(os.path.join(folder, rel_path)):
            return folder
    return app.static_folder


@app.route("/", defaults={"path": ""})
@app.route("/<path:path>", methods=["GET"])
def catch_all(path):
    """Vercel Serverless 및 PWA 정적 파일/페이지 Catch-All 서빙"""
    if path == "manifest.json" or path == "api/manifest.json":
        static_dir = get_static_dir("manifest.json")
        return send_from_directory(static_dir, "manifest.json", mimetype="application/manifest+json")
    if path == "sw.js" or path == "api/sw.js":
        static_dir = get_static_dir("sw.js")
        response = send_from_directory(static_dir, "sw.js", mimetype="application/javascript")
        response.headers["Service-Worker-Allowed"] = "/"
        return response
    if path.startswith("static/") or path.startswith("api/static/"):
        rel_path = path[7:] if path.startswith("static/") else path[11:]
        mimetype = None
        if rel_path.endswith(".css"):
            mimetype = "text/css; charset=utf-8"
        elif rel_path.endswith(".js"):
            mimetype = "application/javascript; charset=utf-8"
        elif rel_path.endswith(".png"):
            mimetype = "image/png"
        elif rel_path.endswith(".svg"):
            mimetype = "image/svg+xml"
        elif rel_path.endswith(".json"):
            mimetype = "application/json"
        elif rel_path.endswith(".ico"):
            mimetype = "image/x-icon"
        static_dir = get_static_dir(rel_path)
        return send_from_directory(static_dir, rel_path, mimetype=mimetype)
    return render_template("index.html")


@app.route("/generate", methods=["POST"])
@app.route("/api/generate", methods=["POST"])
@app.route("/api/index.py/generate", methods=["POST"])
def generate_recipe():
    """레시피 3종 후보 생성 및 유튜브 연동 엔드포인트"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "요청 데이터가 올바르지 않습니다."}), 400

        # 사용자 입력 데이터 추출
        ingredients = data.get("ingredients", "").strip()
        servings = data.get("servings", "1인분").strip()
        cooking_time = data.get("cooking_time", "20분 이내").strip()
        tools = data.get("tools", "기본 조리도구(후라이팬/냄비)").strip()
        allergies = data.get("allergies", "없음").strip()
        preference = data.get("preference", "대중적인 맛").strip()

        # 필수 입력값 검증 (재료 필수)
        if not ingredients:
            return jsonify({"success": False, "error": "보유하고 계신 재료를 1개 이상 입력해 주세요."}), 400

        if not genai_client:
            return jsonify({
                "success": False,
                "error": "Gemini API 키가 설정되지 않았습니다. .env 파일을 확인해 주세요."
            }), 500

        # Gemini 프롬프트 엔지니어링 (3가지 스타일의 다채로운 레시피 생성)
        prompt = f"""
당신은 대한민국 최고의 스타 셰프이자 전문 영양사입니다.
사용자가 제공한 조건을 분석하여, 사용자가 골라 먹을 수 있는 서로 다른 매력의 **3가지 맞춤형 추천 요리 레시피**를 만들어주세요.

[사용자 요청 조건]
- 보유 재료: {ingredients}
- 인원수: {servings}
- 희망 조리시간: {cooking_time}
- 보유 조리도구: {tools}
- 알레르기/비선호 성분: {allergies}
- 선호 음식/스타일: {preference}

[3가지 요리 구성 방향]
1. 첫 번째 메뉴: 가장 빠르고 간단하게 만드는 초간단 스피드 요리 (예: 볶음/덮밥/전)
2. 두 번째 메뉴: 든든하고 깊은 맛의 국물/찌개 또는 정성 요리
3. 세 번째 메뉴: 색다르고 트렌디한 이색 퓨전/별미 요리

반드시 아래 JSON 포맷 형식에 맞춰 한국어로 응답해 주세요. 마크다운 코드블록(```json) 없이 오직 유효한 순수 JSON 문자열만 출력해야 합니다.

{{
  "recipes": [
    {{
      "id": 1,
      "category_tag": "⚡ 초간단 스피드",
      "menu_name": "메뉴 이름 1",
      "one_line_intro": "이 요리의 매력을 담은 한 줄 소개",
      "estimated_time": "15분",
      "servings": "{servings}",
      "difficulty": "초급",
      "nutrition_info": {{
        "calories": "약 380 kcal",
        "carbs": "40g",
        "protein": "22g",
        "fat": "12g",
        "sodium": "580mg",
        "health_summary": "소화가 잘되고 가볍게 즐길 수 있는 균형 식단입니다."
      }},
      "ingredients_list": [
        "재료명 1 (정확한 분량)",
        "재료명 2 (정확한 분량)"
      ],
      "sauce_ratios": [
        "양념 1 (계량 스푼 기준 비율)",
        "양념 2 (계량 스푼 기준 비율)"
      ],
      "cooking_steps": [
        "1단계: 재료 손질 방법 및 팁",
        "2단계: 조리 과정 (불 조절 세기, 가열 시간 명시)",
        "3단계: 마무리 및 플레이팅"
      ],
      "substitute_guide": [
        "대체 가능한 재료 안내"
      ],
      "fail_proof_tips": [
        "절대 실패하지 않는 핵심 팁"
      ]
    }},
    {{
      "id": 2,
      "category_tag": "🍲 든든한 국물/일품",
      "menu_name": "메뉴 이름 2",
      "one_line_intro": "한 줄 소개 2",
      "estimated_time": "20분",
      "servings": "{servings}",
      "difficulty": "초중급",
      "nutrition_info": {{
        "calories": "약 430 kcal",
        "carbs": "45g",
        "protein": "26g",
        "fat": "15g",
        "sodium": "680mg",
        "health_summary": "단백질과 수분이 풍부하여 포만감이 뛰어납니다."
      }},
      "ingredients_list": ["재료 목록"],
      "sauce_ratios": ["양념 비율"],
      "cooking_steps": ["조리 순서"],
      "substitute_guide": ["대체 재료"],
      "fail_proof_tips": ["실패 방지 팁"]
    }},
    {{
      "id": 3,
      "category_tag": "✨ 색다른 별미/퓨전",
      "menu_name": "메뉴 이름 3",
      "one_line_intro": "한 줄 소개 3",
      "estimated_time": "25분",
      "servings": "{servings}",
      "difficulty": "중급",
      "nutrition_info": {{
        "calories": "약 460 kcal",
        "carbs": "50g",
        "protein": "24g",
        "fat": "18g",
        "sodium": "620mg",
        "health_summary": "입맛을 돋우는 풍미 가득한 특별식입니다."
      }},
      "ingredients_list": ["재료 목록"],
      "sauce_ratios": ["양념 비율"],
      "cooking_steps": ["조리 순서"],
      "substitute_guide": ["대체 재료"],
      "fail_proof_tips": ["실패 방지 팁"]
    }}
  ]
}}
"""

        logging.info("Gemini 모델에 3종 레시피 생성 요청 중...")
        last_error = None
        result_data = None

        for model_name in FALLBACK_MODELS:
            try:
                response = genai_client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        temperature=0.75
                    )
                )
                response_text = response.text.strip()

                try:
                    result_data = json.loads(response_text)
                except json.JSONDecodeError:
                    cleaned = response_text.replace("```json", "").replace("```", "").strip()
                    result_data = json.loads(cleaned)

                logging.info(f"모델 '{model_name}'으로 3종 레시피 생성 성공!")
                break
            except Exception as model_err:
                logging.warning(f"모델 '{model_name}' 실패: {model_err}. 다음 모델로 자동 전환합니다.")
                last_error = model_err
                continue

        if not result_data or "recipes" not in result_data:
            raise Exception(f"레시피 데이터 생성에 실패했습니다: {last_error}")

        recipes = result_data.get("recipes", [])

        # 각 레시피마다 유튜브 요리 영상 정보 연동
        for r in recipes:
            menu_name = r.get("menu_name", "")
            r["youtube"] = search_youtube_video(menu_name)

        return jsonify({"success": True, "recipes": recipes})

    except Exception as e:
        logging.error(f"레시피 생성 중 에러 발생: {e}")
        return jsonify({
            "success": False,
            "error": f"레시피를 생성하는 중 문제가 발생했습니다: {str(e)}"
        }), 500


if __name__ == "__main__":
    logging.info(f"AI 맞춤형 레시피 서버 시작: http://127.0.0.1:{PORT}")
    app.run(host="0.0.0.0", port=PORT, debug=True)