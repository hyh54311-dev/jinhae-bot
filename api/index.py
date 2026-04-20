import os
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

# 환경변수에서 API 키 로드
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

app = FastAPI(title="Kakao Admission Chatbot Webhook")

# 정적 파일 서빙 설정 (HTML, CSS, JS)
# Vercel 배포 환경과 로컬 환경 모두 고려
public_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'public')
if os.path.exists(public_path):
    app.mount("/static", StaticFiles(directory=public_path), name="static")

@app.get("/")
async def read_index():
    index_file = os.path.join(public_path, 'index.html')
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return {"message": "진해고등학교 입학 상담 챗봇 서버가 작동 중입니다."}

# 지식 베이스 파일 로드 함수
def load_knowledge():
    try:
        # api 폴더 내의 knowledge.txt 파일 읽기
        knowledge_path = os.path.join(os.path.dirname(__file__), 'knowledge.txt')
        with open(knowledge_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        print(f"지식 베이스 파일 로드 실패: {e}")
        return "입학 관련 기본 정보가 없습니다."

KNOWLEDGE_BASE = load_knowledge()

# 시스템 프롬프트 (입학 상담원 역할 및 기본 지침 설정)
SYSTEM_PROMPT = f"""너는 '진해고등학교'의 친절하고 센스 있는 입학 상담 챗봇이야 😊. 
지원자나 학부모의 질문에 항상 존댓말을 사용하며, 다정하고 희망찬 어조로 명확하게 답변해 줘.

[가장 중요한 답변 규칙 🚨]
1. 아래 제공된 [진해고등학교 입학 안내 자료(지식 베이스)]를 바탕으로만 정확하게 답변을 작성해.
2. 지식 베이스에 없는 내용이나 자의적으로 꾸며낸 정보(거짓말)는 절대 답변하지 마. 모르는 내용이나 확답할 수 없는 내용이라면, "해당 내용은 입학처(055-546-2260) 또는 교무실로 문의해 주시면 정확한 안내를 받으실 수 있습니다."라고 안내해 줘.
3. 사용자의 질문이 '기숙사'와 관련된 내용이라면, 네가 아는 선에서 먼저 친절하게 답변을 한 후, 답변 맨 밑에 줄바꿈을 하고 반드시 담당 부서의 전화번호를 안내해 줘. (예: "기숙사 관련 추가 문의 사항은 기숙사부 000-000-0000 으로 연락 주시면 상세히 상담해 드립니다!")

[진해고등학교 입학 안내 자료(지식 베이스)]
{KNOWLEDGE_BASE}
"""

def generate_gemini_response(prompt: str) -> str:
    """Gemini API를 호출하여 답변을 생성합니다."""
    if not GEMINI_API_KEY:
         return "죄송합니다. 봇 서버에 오류가 발생했습니다. (API 키 미설정)"
         
    try:
        # 모델 설정 (가장 빠르고 성능이 좋은 최신 모델 사용)
        model = genai.GenerativeModel('gemini-3.1-pro') 
        full_prompt = f"{SYSTEM_PROMPT}\n\n사용자 질문: {prompt}\n답변:"
        response = model.generate_content(full_prompt)
        return response.text.strip()
    except Exception as e:
        print(f"Gemini API Error: {e}")
        return "죄송합니다. 서버 처리 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요."

@app.post("/api/chat")
async def kakao_chat(request: Request):
    """카카오 i 오픈빌더에서 오는 스킬 데이터를 처리합니다."""
    payload = await request.json()
    
    # 카카오톡 발화 내용 추출 (오픈빌더 Payload 스펙)
    try:
        user_utterance = payload.get("userRequest", {}).get("utterance", "")
    except Exception:
        user_utterance = ""

    # 질문이 비어있을 경우 예외 처리
    if not user_utterance:
        bot_responseText = "말씀하신 내용을 잘 이해하지 못했어요. 다시 한 번 질문해 주시겠어요?"
    else:
        # Gemini API를 통해 답변 생성
        bot_responseText = generate_gemini_response(user_utterance)
    
    # 카카오 i 오픈빌더 응답 포맷 (SimpleText 형식)
    kakao_response = {
        "version": "2.0",
        "template": {
            "outputs": [
                {
                    "simpleText": {
                        "text": bot_responseText
                    }
                }
            ]
        }
    }
    
    return JSONResponse(content=kakao_response)

# Vercel 환경이 아닌 로컬 테스트 시 실행되는 설정
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.index:app", host="0.0.0.0", port=8000, reload=True)
