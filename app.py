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


@app.after_request
def add_cors_headers(response):
    """모든 요청에 CORS 허용 헤더 추가"""
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type,Authorization"
    response.headers["Access-Control-Allow-Methods"] = "GET,POST,OPTIONS"
    return response


@app.route("/", defaults={"path": ""}, methods=["GET", "POST", "OPTIONS"])
@app.route("/<path:path>", methods=["GET", "POST", "OPTIONS"])
def catch_all(path):
    """Vercel Serverless 및 PWA 정적 파일/페이지/API Catch-All 서빙"""
    if request.method == "OPTIONS":
        return "", 200

    # POST 요청이거나 generate 경로인 경우 레시피 생성 API로 직결
    if request.method == "POST" or path == "generate" or path.endswith("/generate") or path.endswith("generate"):
        return generate_recipe()

    if path == "manifest.json" or path.endswith("manifest.json"):
        static_dir = get_static_dir("manifest.json")
        response = send_from_directory(static_dir, "manifest.json", mimetype="application/manifest+json")
        response.headers["Content-Type"] = "application/manifest+json; charset=utf-8"
        return response

    if path == "sw.js" or path.endswith("sw.js"):
        static_dir = get_static_dir("sw.js")
        response = send_from_directory(static_dir, "sw.js", mimetype="application/javascript")
        response.headers["Content-Type"] = "application/javascript; charset=utf-8"
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
            mimetype = "application/json; charset=utf-8"
        elif rel_path.endswith(".ico"):
            mimetype = "image/x-icon"
        static_dir = get_static_dir(rel_path)
        return send_from_directory(static_dir, rel_path, mimetype=mimetype)

    return render_template("index.html")


@app.route("/generate", methods=["GET", "POST", "OPTIONS"])
@app.route("/api/generate", methods=["GET", "POST", "OPTIONS"])
@app.route("/api/index.py/generate", methods=["GET", "POST", "OPTIONS"])
def generate_recipe():
    """레시피 3종 후보 생성 및 유튜브 연동 엔드포인트"""
    if request.method == "OPTIONS":
        return "", 200
    if request.method == "GET":
        return jsonify({"success": True, "message": "Recipe API is active."})
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

        # Gemini 프롬프트 엔지니어링 (3가지 스타일의 고품질 맞춤형 셰프 레시피 생성)
        prompt = f"""
당신은 대한민국 최고의 스타 셰프이자 전문 영양사입니다.
사용자가 입력한 냉장고 재료와 요청 조건을 바탕으로, 집에서도 손쉽고 완벽하게 성공할 수 있는 **서로 다른 매력의 3가지 추천 요리 레시피**를 만들어주세요.

[사용자 요청 조건]
- 보유 식재료: {ingredients}
- 인원수: {servings}
- 희망 조리시간: {cooking_time}
- 보유 조리도구: {tools}
- 제외/알레르기 성분: {allergies}
- 희망 요리 스타일: {preference}

[3가지 메뉴 구성 원칙]
1. 첫 번째 메뉴 (⚡ 초간단 스피드): 가장 빠르고 손쉽게 뚝딱 만드는 볶음/덮밥/전/한그릇 요리
2. 두 번째 메뉴 (🍲 든든한 정성 한 끼): 깊은 감칠맛의 국물, 찌개, 조림, 또는 든든한 밥도둑 메인 요리
3. 세 번째 메뉴 (✨ 트렌디 별미/퓨전): 색다르고 입맛을 돋우는 이색 브런치/야식/퓨전 별미 요리

[응답 규칙]
- 모든 레시피는 실제로 조리 가능한 현실적이고 맛있는 레시피여야 합니다.
- 양념 비율은 밥숟가락(T), 찻숟가락(t), 종이컵 기준으로 정확히 계량해 주세요.
- 조리 순서는 불 세기(강불/중불/약불)와 시간(분 단위)을 명확하게 기재해 주세요.
- 마크다운(```json) 없이 순수 JSON 포맷으로 한국어로만 응답해 주세요.

{{
  "recipes": [
    {{
      "id": 1,
      "category_tag": "⚡ 초간단 스피드",
      "menu_name": "매력적이고 군침도는 실제 요리명 1",
      "one_line_intro": "이 요리의 핵심 매력과 맛을 설명하는 감성적인 한 줄 소개",
      "estimated_time": "15분",
      "servings": "{servings}",
      "difficulty": "초급",
      "nutrition_info": {{
        "calories": "약 380 kcal",
        "carbs": "42g",
        "protein": "24g",
        "fat": "12g",
        "sodium": "540mg",
        "health_summary": "소화가 편안하고 활력을 돋우는 균형 잡힌 영양 식단입니다."
      }},
      "ingredients_list": [
        "주재료 1 (예: 신김치 1컵, 송송 썬 것)",
        "주재료 2 (예: 계란 2개)",
        "부재료 (예: 대파 1/2대)"
      ],
      "sauce_ratios": [
        "진간장 1큰술",
        "설탕 1/2큰술",
        "참기름 1큰술",
        "통깨 약간"
      ],
      "cooking_steps": [
        "1단계: 재료를 먹기 좋은 크기로 썰어 준비합니다.",
        "2단계: 팬에 식용유 1큰술을 두르고 중불에서 파를 볶아 향을 냅니다.",
        "3단계: 나머지 재료와 양념장을 넣고 센불에서 3분간 빠르게 볶아 완성합니다."
      ],
      "substitute_guide": [
        "스팸 대신 참치캔이나 베이컨을 사용해도 아주 맛있습니다.",
        "대파가 없으면 쪽파나 양파로 대체 가능합니다."
      ],
      "fail_proof_tips": [
        "센불에서 너무 오래 볶으면 양념이 탈 수 있으니 중약불로 조절해 주세요.",
        "마지막에 참기름을 둘러주면 고소한 풍미가 2배로 살아납니다."
      ]
    }},
    {{
      "id": 2,
      "category_tag": "🍲 든든한 정성 한 끼",
      "menu_name": "매력적인 실제 요리명 2",
      "one_line_intro": "깊고 진한 풍미를 자랑하는 든든한 밥도둑 요리",
      "estimated_time": "20분",
      "servings": "{servings}",
      "difficulty": "초중급",
      "nutrition_info": {{
        "calories": "약 450 kcal",
        "carbs": "46g",
        "protein": "28g",
        "fat": "16g",
        "sodium": "680mg",
        "health_summary": "단백질과 수분이 듬뿍 담겨 속을 든든하게 채워줍니다."
      }},
      "ingredients_list": ["구체적인 재료와 분량"],
      "sauce_ratios": ["정확한 양념 비율"],
      "cooking_steps": ["상세한 단계별 조리 순서"],
      "substitute_guide": ["대체 가능한 식재료 팁"],
      "fail_proof_tips": ["실패 없는 맛보장 꿀팁"]
    }},
    {{
      "id": 3,
      "category_tag": "✨ 트렌디 별미/퓨전",
      "menu_name": "매력적인 실제 요리명 3",
      "one_line_intro": "입맛을 돋우는 이색적이고 특별한 한 접시",
      "estimated_time": "25분",
      "servings": "{servings}",
      "difficulty": "중급",
      "nutrition_info": {{
        "calories": "약 490 kcal",
        "carbs": "52g",
        "protein": "22g",
        "fat": "19g",
        "sodium": "610mg",
        "health_summary": "기분 전환을 돕는 풍성하고 즐거운 식사입니다."
      }},
      "ingredients_list": ["구체적인 재료와 분량"],
      "sauce_ratios": ["정확한 양념 비율"],
      "cooking_steps": ["상세한 단계별 조리 순서"],
      "substitute_guide": ["대체 가능한 식재료 팁"],
      "fail_proof_tips": ["실패 없는 맛보장 꿀팁"]
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