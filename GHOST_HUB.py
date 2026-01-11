import streamlit as st
import google.generativeai as genai
import requests
import random
import os
import json
import re
import sys
import io
from duckduckgo_search import DDGS
from dotenv import load_dotenv
from datetime import datetime

# ==========================================
# 1. 환경 설정
# ==========================================
load_dotenv()
sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.detach(), encoding='utf-8')

GENAI_API_KEY = os.getenv("GEMINI_API_KEY") or st.secrets.get("GEMINI_API_KEY")
UNSPLASH_ACCESS_KEY = os.getenv("UNSPLASH_ACCESS_KEY") or st.secrets.get("UNSPLASH_ACCESS_KEY")

if not GENAI_API_KEY:
    st.error("🚨 GEMINI_API_KEY를 .env 파일에서 찾을 수 없습니다.")
    st.stop()

genai.configure(api_key=GENAI_API_KEY)
model = genai.GenerativeModel('gemini-3-flash-preview')

# ==========================================
# 2. 공통 함수
# ==========================================

def hunt_realtime_info(keyword):
    """실시간 정보 수집"""
    try:
        with DDGS() as ddgs:
            results = list(ddgs.news(keyword, region='kr-kr', safesearch='off', timelimit='w', max_results=6))
            if not results:
                results = list(ddgs.text(keyword, region='kr-kr', max_results=6))
            context = ""
            for r in results:
                context += f"정보원: {r.get('title', '')}\n핵심내용: {r.get('body', '')}\n\n"
            return context if context else "최신 트렌드 분석을 기반으로 집필합니다."
    except:
        return "최신 트렌드 분석을 기반으로 집필합니다."

def clean_all_tags(text):
    """HTML 태그 제거"""
    text = re.sub(r'<[^>]*>', '', text)
    text = text.replace("**", "").replace("__", "").replace("*", "").replace("#", "")
    return text.strip()

def remove_markdown(text):
    """마크다운 완전 제거"""
    text = text.replace('#', '')
    text = text.replace('*', '')
    text = text.replace('**', '')
    text = text.replace('__', '')
    return text

def get_ftc_text(url):
    """공정위 문구"""
    if not url: return ""
    u = url.lower()
    if "coupang" in u: return "이 포스팅은 쿠팡 파트너스 활동의 일환으로, 이에 따른 일정액의 수수료를 제공받습니다."
    if "naver" in u or "smartstore" in u: return "이 포스팅은 네이버 쇼핑커넥트 활동의 일환으로, 판매 발생 시 수수료를 제공받습니다."
    if "oliveyoung" in u: return "이 포스팅은 올리브영 쇼핑 큐레이터 활동의 일환으로, 판매 발생시 수수료를 제공받습니다."
    return "이 포스팅은 제휴 마케팅 활동의 일환으로 커미션를 받습니다."

def get_unsplash_images(keyword, count=5):
    """Unsplash에서 이미지 검색"""
    if not UNSPLASH_ACCESS_KEY:
        st.warning("⚠️ UNSPLASH_ACCESS_KEY가 .env 파일에 없습니다. 이미지를 추가하려면 API 키를 설정하세요.")
        return []
    try:
        url = "https://api.unsplash.com/search/photos"
        params = {"query": keyword, "per_page": count, "client_id": UNSPLASH_ACCESS_KEY}
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code != 200:
            st.error(f"❌ Unsplash API 오류: {response.status_code} - {response.text[:100]}")
            return []
            
        data = response.json()
        images = []
        for photo in data.get('results', []):
            images.append({
                'url': photo['urls']['regular'],
                'photographer': photo['user']['name'],
                'photo_link': photo['links']['html']
            })
        
        if not images:
            st.info(f"💡 '{keyword}' 키워드로 이미지를 찾지 못했습니다.")
        else:
            st.success(f"✅ Unsplash에서 이미지 {len(images)}장 찾음!")
            
        return images
    except Exception as e:
        st.error(f"❌ Unsplash 이미지 오류: {e}")
        return []

def format_image_html(img):
    """이미지 HTML 생성 (출처 포함)"""
    return f'''<div style="margin:30px 0; text-align:center;">
<img src="{img['url']}" alt="관련 이미지" style="max-width:100%; border-radius:8px; box-shadow:0 4px 8px rgba(0,0,0,0.1);">
<p style="font-size:12px; color:#666; margin-top:8px;">
Photo by <a href="{img['photo_link']}" target="_blank" style="color:#666; text-decoration:underline;">{img['photographer']}</a> on <a href="https://unsplash.com" target="_blank" style="color:#666; text-decoration:underline;">Unsplash</a>
</p></div>'''

# ==========================================
# 3. 네이버 수익형
# ==========================================

NAVER_PROFIT_PERSONAS = [
    {"role": "30대 워킹맘", "tone": "친근한 존댓말", "keywords": ["진짜", "완전", "대박", "리얼", "솔직히"], "emoji_style": "😊 💕 👍 ✨ 🔥"},
    {"role": "20대 직장인", "tone": "가벼운 반말", "keywords": ["ㅇㅁ", "가성비", "꿀템", "핵이득", "존맛"], "emoji_style": "🔥 💯 ✅ 💸 ⚡"},
    {"role": "40대 구매 전문가", "tone": "정중한 존댓말", "keywords": ["실제로", "확실히", "분명", "경험상", "추천드립니다"], "emoji_style": "✅ 💡 📊 👌 ⭐"},
    {"role": "블로그 마니아", "tone": "설명형 존댓말", "keywords": ["정리해드릴게요", "알려드립니다", "확인해보세요", "참고하세요"], "emoji_style": "📌 ✏️ 💬 🎯 📝"},
    {"role": "소비 분석가", "tone": "분석적 존댓말", "keywords": ["비교해보면", "데이터상", "실측", "결과적으로"], "emoji_style": "📈 🔍 💰 🎓 ⚖️"}
]

NAVER_PROFIT_STRUCTURES = {
    1: {"name": "스토리텔링형", "sections": ["개인 경험담", "문제 발견", "제품 만남", "사용 과정", "결과/변화"]},
    2: {"name": "데이터 분석형", "sections": ["시장 현황", "수치 비교", "스펙 분석", "가격 분석", "종합 평가"]},
    3: {"name": "비교 대결형", "sections": ["경쟁 제품들", "1차 비교", "심층 비교", "상황별 추천", "최종 승자"]},
    4: {"name": "폭로 고발형", "sections": ["충격 사실", "업계 속사정", "진실 분석", "대안 제시", "행동 촉구"]},
    5: {"name": "Q&A 해결형", "sections": ["베스트 질문", "오해 바로잡기", "핵심 답변", "추가 팁", "최종 정리"]}
}

CTA_HOOKS = [
    "🚨 이거 모르고 사면 손해!",
    "⏰ 지금만 이 가격! 내일부터 인상",
    "💡 알 사람만 아는 숨겨진 혜택",
    "🚨 뒤늦게 알고 후회하지 마세요",
    "⚡ 지금 안 보면 기회 날아갑니다",
    "🔥 놓치면 후회할 특가!",
    "✨ 현명한 선택은 지금!",
    "💝 최저가 타이밍 놓치지 마세요"
]

DIVIDERS = [
    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
    "────────────────────────────",
    "◈◈◈◈◈◈◈◈◈◈◈◈◈◈◈◈◈◈◈◈◈◈◈◈◈◈◈◈",
    "============================================"
]

def get_naver_h3(text):
    """네이버 19px 소제목 (줄바꿈 확보)"""
    return f'\n\n{random.choice(DIVIDERS)}\n<span style="font-size: 19px; font-weight: bold; color: #000000;">📍 {text}</span>\n\n'

def generate_naver_profit_prompt(keyword, product, url, facts, persona, structure):
    """네이버 수익형 프롬프트"""
    return f"""
당신은 지금 {persona["role"]}입니다.

[철칙 - 위반 시 즉시 폐기]
1. 마크다운(#, *, **) 절대 금지. 오직 <b>태그만!
2. "안녕하세요", "오늘은", "알아보겠습니다" 금지
3. 자기소개 절대 금지
4. 쿠팡 언급 절대 금지
5. 마무리 멘트 절대 금지 ("결론", "마무리", "마치며")
6. 날짜 노출 절대 금지

[작성 정보]
- 키워드: {keyword}
- 제품: {product}
- 링크: {url}
- 실시간 이슈: {facts}
- 말투: {persona["tone"]}
- 이모지: {persona["emoji_style"]}

[글자수] 정확히 1800~2400자

[JSON 응답]
{{
    "title": "제목",
    "content": "본문",
    "hashtags": "7개"
}}

[제목 작성법 - 다양한 후킹!]
반드시 아래 8가지 중 1개 (골고루 사용):
1. "{keyword} 이거 모르면 손해"
2. "알 사람만 아는 {keyword} 숨겨진 진실"
3. "{keyword} 샀다가 멘붕 온 이유"
4. "업계 10년이 폭로하는 {keyword} 비밀"
5. "{keyword} vs {{경쟁품}}, 충격적 결과"
6. "{keyword} 기대했는데 완전 반전"
7. "{keyword} 지금 안 보면 후회합니다"
8. "{keyword} 진실은 이것, 놓치지 마세요"

제목 규칙:
- {keyword} 반드시 포함
- 손해/후회/충격/진실/비밀 단어 포함
- 15-25자
- 이모지 금지

[절대 금지 - 자기소개!]
❌ "안녕하세요"
❌ "저는 ~입니다"
❌ "40대", "20대", "전문가", "블로거" 단어
❌ "~로서", "~로써"
❌ 본인 역할/나이/직업 언급
→ 바로 본론 시작!

[도입부] 첫 5문장이 생명!
- 첫 문장 5단어 이내
- 구체적 숫자 2개+
- 이모지 1~2개
- 자기소개 없이 바로 팩트!

[본문 구성]
{", ".join(structure["sections"])}로 전개

각 섹션:
- 소제목: [H3]제목[/H3]
- 이모지 자연스럽게

[CTA 배치]
[[CTA_1]]을 3번째 섹션 후
[[CTA_2]]를 FAQ 직전
총 2번

[FAQ 필수 3개]
Q1: 가장 큰 실수
Q2: 꼭 확인할 것
Q3: 지금 사야 하는 이유

[마무리]
FAQ 후 2~3문장:
"지금 안 하면 후회", "{{금액}}원 날리기 싫으면 지금"
→ 행동 촉구만! 정리/요약 금지!

[해시태그] 7개 (이모지 없이)

JSON만 출력하세요.
"""

def render_naver_profit():
    """네이버 수익형 UI"""
    st.title("💀 네이버 수익형 v1.1: FOMO 극대화")
    
    if 'naver_profit_content' not in st.session_state: 
        st.session_state.naver_profit_content = ""
    if 'naver_profit_display' not in st.session_state: 
        st.session_state.naver_profit_display = ""
    
    col1, col2 = st.columns(2)
    with col1:
        keyword = st.text_input("💎 키워드", key="naver_profit_kw", placeholder="예: 무선 청소기 추천")
        product = st.text_input("📦 상품명", key="naver_profit_prod", placeholder="예: 다이슨 V15")
    with col2:
        url = st.text_input("🔗 제휴 링크", key="naver_profit_url", placeholder="http://...")
    
    # 입력 변경 감지 - 자동 초기화
    current_input = f"{keyword}_{product}_{url}"
    if 'naver_profit_last_input' not in st.session_state:
        st.session_state.naver_profit_last_input = ""
    
    if current_input != st.session_state.naver_profit_last_input:
        st.session_state.naver_profit_content = ""
        st.session_state.naver_profit_display = ""
        st.session_state.naver_profit_last_input = current_input
    
    if st.button("🚀 FOMO 극대화 원고 생성", key="naver_profit_btn"):
        if not keyword or not product or not url:
            st.warning("⚠️ 모든 정보를 입력해주세요.")
        else:
            with st.spinner('페르소나 선택 중...'):
                try:
                    persona = random.choice(NAVER_PROFIT_PERSONAS)
                    structure_id = random.randint(1, 5)
                    structure = NAVER_PROFIT_STRUCTURES[structure_id]
                    
                    facts = hunt_realtime_info(keyword)
                    prompt = generate_naver_profit_prompt(keyword, product, url, facts, persona, structure)
                    
                    st.info(f"🎭 페르소나: {persona['role']} | 📖 구조: {structure['name']}")
                    
                    response = model.generate_content(prompt)
                    raw_text = response.text
                    
                    json_match = re.search(r'\{.*\}', raw_text, re.DOTALL)
                    if json_match:
                        data = json.loads(json_match.group())
                        title = data.get('title', f'{keyword} 후기')
                        content = data.get('content', '')
                        
                        # 마크다운 제거
                        content = remove_markdown(content)
                        title = remove_markdown(title)
                        
                        # 소제목 변환 (H3 형식)
                        content = re.sub(r'\[H3\](.*?)\[/H3\]', lambda m: get_naver_h3(m.group(1)), content)
                        
                        # CTA 생성 (2개 다른 후킹 + 링크)
                        hook1 = random.choice(CTA_HOOKS)
                        hook2 = random.choice([h for h in CTA_HOOKS if h != hook1])
                        
                        cta1_html = f'<div style="margin: 30px 0; padding: 20px; border: 3px solid #000; border-radius: 5px;"><p style="font-size: 15px; color: #000; margin: 0 0 10px 0; font-weight: bold;">{hook1}</p><p style="font-size: 16px; color: #000; margin: 0 0 10px 0; font-weight: bold;">👉 {product} 최저가 & 혜택 확인하기</p><p style="font-size: 14px; margin: 0;"><a href="{url}" target="_blank" style="color: #000; text-decoration: underline;">🔗 {url[:50]}...</a></p></div>'
                        
                        cta2_html = f'<div style="margin: 30px 0; padding: 20px; border: 3px solid #000; border-radius: 5px;"><p style="font-size: 15px; color: #000; margin: 0 0 10px 0; font-weight: bold;">{hook2}</p><p style="font-size: 16px; color: #000; margin: 0 0 10px 0; font-weight: bold;">👉 {product} 지금 바로 구매하기</p><p style="font-size: 14px; margin: 0;"><a href="{url}" target="_blank" style="color: #000; text-decoration: underline;">🔗 {url[:50]}...</a></p></div>'
                        
                        content = content.replace("[[CTA_1]]", cta1_html, 1)
                        content = content.replace("[[CTA_2]]", cta2_html, 1)
                        content = re.sub(r'\[\[CTA_\d+\]\]', '', content)
                        
                        disclosure = get_ftc_text(url)
                        
                        final = f"""<div style="font-family: 'Nanum Gothic', sans-serif; font-size: 15px; line-height: 1.8; color: #000;">
{disclosure}

<h1 style="font-size: 24px; font-weight: bold; color: #000; margin: 20px 0; padding-bottom: 10px; border-bottom: 2px solid #000;">{title}</h1>

{content}

<div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #ddd; color: #000; font-weight: bold;">{data.get('hashtags', '')}</div>
</div>"""
                        
                        st.session_state.naver_profit_content = final
                        st.session_state.naver_profit_display = clean_all_tags(final)
                    else:
                        st.error("JSON 형식을 찾을 수 없습니다.")
                except Exception as e:
                    st.error(f"오류: {e}")
    
    if st.session_state.naver_profit_display:
        st.divider()
        st.subheader("📋 원고 확인")
        st.text_area("내용 확인", value=st.session_state.naver_profit_display, height=500, key="naver_profit_display_area")
        
        safe = st.session_state.naver_profit_content.replace("`", "\\`").replace("$", "\\$")
        safe = re.sub(r'>\s*\n\s*<', '><', safe)
        html_code = safe.replace("\n", "<br>")
        
        st.components.v1.html(f"""
            <button onclick="copyRich()" style="width:100%; padding:20px; background:#111; color:#00FF7F; border:2px solid #00FF7F; border-radius:12px; font-weight:bold; cursor:pointer; font-size:18px;">
                📋 네이버 블로그 서식 포함 복사
            </button>
            <script>
            function copyRich() {{
                const html = `{html_code}`;
                const blob = new Blob([html], {{ type: "text/html" }});
                const data = [new ClipboardItem({{ "text/html": blob }})];
                navigator.clipboard.write(data).then(() => alert("✅ 복사 완료!"));
            }}
            </script>
        """, height=100)

# ==========================================
# 4. 네이버 정보성
# ==========================================

NAVER_INFO_PERSONAS = [
    {"role": "전문 칼럼니스트", "tone": "정중한 존댓말", "keywords": ["분석하면", "살펴보면", "알 수 있습니다"]},
    {"role": "정보 큐레이터", "tone": "친절한 설명", "keywords": ["정리하면", "핵심은", "중요한 점은"]},
    {"role": "업계 전문가", "tone": "전문적 존댓말", "keywords": ["실제로", "데이터상", "경험상"]}
]

INFO_TYPES = [
    "문장형_체크리스트",
    "표_위주",
    "단답형_리스트",
    "박스형_QA강조",
    "번호목록_속성표"
]

def get_naver_info_h3(text):
    """네이버 정보성 19px 소제목 (배경색 없음)"""
    styles = [
        'border-left: 10px solid #2c5aa0; padding-left: 15px; border-bottom: 1px solid #eee; margin: 40px 0 20px 0;',
        'border-top: 4px solid #2c5aa0; padding: 15px; border-bottom: 1px solid #eee; margin: 40px 0 20px 0;',
        'display: inline-block; padding: 5px 15px; border: 2px solid #2c5aa0; color: #2c5aa0; border-radius: 20px; margin: 40px 0 20px 0; font-weight: bold;'
    ]
    return f"\n\n<h3 style='font-size:19px; font-weight:bold; color:#111; {random.choice(styles)}'>{text}</h3>\n\n"

def generate_naver_info_prompt(keyword, facts, persona, info_type):
    """네이버 정보성 프롬프트"""
    type_instructions = {
        "문장형_체크리스트": "☑️ 항목1입니다. 설명을 2-3문장으로...",
        "표_위주": "<table>로 체크리스트와 속성을 정리",
        "단답형_리스트": "✅ 항목1 (1줄로 짧게)",
        "박스형_QA강조": "<div> 박스에 체크리스트 + Q&A 5개",
        "번호목록_속성표": "1. 항목1\n2. 항목2 + <table>속성표</table>"
    }
    
    return f"""
당신은 {persona["role"]}입니다.

[철칙]
1. 마크다운(#, *, **) 절대 금지
2. AI 인사말 금지
3. 자기소개 금지 ("안녕하세요", "저는", "~입니다" 금지)
4. 마무리 멘트 금지
5. 날짜 노출 금지
6. 배경색 절대 금지! (네이버 깨짐)

[작성 정보]
- 키워드: {keyword}
- 정보: {facts}
- 말투: {persona["tone"]}
- 형태: {info_type}

[글자수] 정확히 1800~2400자

[제목 - 정보성 후킹!]
돈 금액 사용 금지! 아래 패턴 사용:
- "{keyword} 완전 정리 (이것만 알면 끝)"
- "{keyword} 핵심 총정리"
- "{keyword} 꼭 알아야 할 모든 것"
- "{keyword} 처음부터 끝까지"
- "{keyword} 이것만 보세요"
예: "건강보험 완전 정리 (이것만 알면 끝)"

[형태: {info_type}]
{type_instructions[info_type]}

[소제목 형식 - 반드시 준수!]
모든 소제목은 [H3]제목내용[/H3] 형식으로 작성하세요.
예: [H3]핵심 체크리스트[/H3]
    [H3]속성 비교표[/H3]

[키워드 강조]
{keyword} 단어가 나올 때마다 <b>{keyword}</b>로 강조하세요.

[필수 섹션]
1. 체크리스트 (형태에 맞게)
   ⚠️ 배경색 절대 금지!
   
2. 속성표 (형태에 맞게)
   <table style="width:100%; border-collapse:collapse; margin:20px 0;">
   <tr><th style="border:1px solid #ddd; padding:10px;">항목</th></tr>
   ⚠️ 배경색 절대 금지!
   
3. Q&A 3~5개
   [H3]자주 듣는 질문[/H3] 다음 줄바꿈 후:
   
   <b style="color:#2c5aa0;">Q1. 질문?</b><br>
   A1. 답변...
   
   반드시 소제목 닫은 후 2줄 띄우고 Q1 시작!

[JSON 응답]
{{
    "title": "강력한 후킹 제목",
    "content": "본문",
    "hashtags": "7개"
}}

JSON만 출력하세요.
"""

def render_naver_info():
    """네이버 정보성 UI"""
    st.title("🟢 네이버 정보성 v1.1: 형태 다양화")
    
    if 'naver_info_content' not in st.session_state: 
        st.session_state.naver_info_content = ""
    if 'naver_info_display' not in st.session_state: 
        st.session_state.naver_info_display = ""
    
    keyword = st.text_input("💎 키워드", key="naver_info_kw", placeholder="예: 건강보험 환급 방법")
    
    if st.button("🚀 전문 칼럼 생성", key="naver_info_btn"):
        if not keyword:
            st.warning("⚠️ 키워드를 입력해주세요.")
        else:
            with st.spinner('전문가 페르소나 접속 중...'):
                try:
                    persona = random.choice(NAVER_INFO_PERSONAS)
                    info_type = random.choice(INFO_TYPES)
                    facts = hunt_realtime_info(keyword)
                    prompt = generate_naver_info_prompt(keyword, facts, persona, info_type)
                    
                    st.info(f"🎭 페르소나: {persona['role']} | 📊 형태: {info_type}")
                    
                    response = model.generate_content(prompt)
                    raw_text = response.text
                    
                    json_match = re.search(r'\{.*\}', raw_text, re.DOTALL)
                    if json_match:
                        data = json.loads(json_match.group())
                        title = data.get('title', f'{keyword} 완전 정리')
                        content = data.get('content', '')
                        
                        # 마크다운 제거
                        content = remove_markdown(content)
                        title = remove_markdown(title)
                        
                        # 소제목 변환 (H3 형식)
                        content = re.sub(r'\[H3\](.*?)\[/H3\]', lambda m: get_naver_info_h3(m.group(1)), content)
                        
                        # Unsplash 이미지 삽입 (5-7장)
                        images = get_unsplash_images(keyword, 7)
                        if images:
                            paragraphs = content.split('</h3>')
                            if len(paragraphs) >= 5:
                                result = ""
                                for i, para in enumerate(paragraphs[:-1]):
                                    result += para + '</h3>'
                                    if i < len(images):
                                        result += format_image_html(images[i])
                                result += paragraphs[-1]
                                content = result
                        
                        final = f"""<div style="font-family: 'Nanum Gothic', sans-serif; font-size: 15px; line-height: 1.8; color: #000;">
<h1 style="font-size: 24px; font-weight: bold; color: #000; margin: 20px 0; padding-bottom: 10px; border-bottom: 2px solid #2c5aa0;">{title}</h1>

{content}

<div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #ddd; color: #000; font-weight: bold;">{data.get('hashtags', '')}</div>
</div>"""
                        
                        st.session_state.naver_info_content = final
                        st.session_state.naver_info_display = clean_all_tags(final)
                    else:
                        st.error("JSON 형식을 찾을 수 없습니다.")
                except Exception as e:
                    st.error(f"오류: {e}")
    
    if st.session_state.naver_info_display:
        st.divider()
        st.subheader("📋 원고 확인")
        st.text_area("내용 확인", value=st.session_state.naver_info_display, height=500, key="naver_info_display_area")
        
        safe = st.session_state.naver_info_content.replace("`", "\\`").replace("$", "\\$")
        safe = re.sub(r'>\s*\n\s*<', '><', safe)
        html_code = safe.replace("\n", "<br>")
        
        st.components.v1.html(f"""
            <button onclick="copyRich()" style="width:100%; padding:20px; background:#03cf5d; color:white; border:none; border-radius:12px; font-weight:bold; cursor:pointer; font-size:18px;">
                🟢 전문가 칼럼 복사하기
            </button>
            <script>
            function copyRich() {{
                const html = `{html_code}`;
                const blob = new Blob([html], {{ type: "text/html" }});
                const data = [new ClipboardItem({{ "text/html": blob }})];
                navigator.clipboard.write(data).then(() => alert("✅ 복사 완료!"));
            }}
            </script>
        """, height=100)

# ==========================================
# 5. 티스토리 정보성
# ==========================================

def get_premium_style():
    """p.py 디자인 스킬"""
    color = "#{:06x}".format(random.randint(0, 0x777777))
    styles = [
        f'border-left: 15px solid {color}; border-bottom: 2px solid {color}; padding: 10px 15px; background: #f8f9fa; font-weight: bold;',
        f'background: linear-gradient(to right, {color}, white); color: white; padding: 12px 20px; border-radius: 5px; box-shadow: 3px 3px 5px rgba(0,0,0,0.1);',
        f'border: 2px solid {color}; padding: 15px; border-left: 10px solid {color}; border-radius: 0 10px 10px 0; background: #ffffff;',
        f'border-top: 1px solid #ddd; border-bottom: 3px double {color}; padding: 10px 0; font-size: 1.5em;'
    ]
    return random.choice(styles)

TISTORY_INFO_PERSONAS = [
    {"role": "트렌드 분석가", "tone": "세련된 존댓말"},
    {"role": "콘텐츠 큐레이터", "tone": "친근한 존댓말"},
    {"role": "정보 전문가", "tone": "전문적 존댓말"}
]

def generate_tistory_info_prompt(keyword, facts, persona):
    """티스토리 정보성 프롬프트"""
    return f"""
당신은 {keyword}에 대한 {persona["role"]}입니다.

[절대 규칙 - 매우 중요!]
1. 🚫 {keyword} 주제에서 절대 벗어나지 마세요
2. 🚫 관련 없는 경제/투자/전략 이야기 금지
   예시 금지:
   - 연예인 은퇴 → 경제/투자 ❌
   - 건강보험 → 부동산 ❌
   - 요리 레시피 → 주식 전망 ❌
3. 🚫 도입부부터 {keyword}만 다루세요
4. 🚫 억지로 미래 예측 넣지 마세요
5. 🚫 글자수 채우려고 주제 벗어나지 마세요

[작성 정보]
- 주제: {keyword} (이것만!)
- 정보: {facts}
- 말투: {persona["tone"]}

[글자수] 정확히 1800~2400자

[제목 - 강력한 후킹!]
예: "{keyword} 이거 모르면 못 삽니다"

[구조]
도입: {keyword} 관련 후킹
본문: 5개 소제목 [H3]제목[/H3]
- {keyword}와 직접 관련된 내용만
- <b>태그</b> 강조

[JSON 응답]
{{
    "title": "강력한 후킹 제목",
    "content": "본문",
    "hashtags": "7개"
}}

JSON만 출력하세요.
"""

def render_tistory_info():
    """티스토리 정보성 UI"""
    st.title("🟠 티스토리 정보성 v1.1: 주제 집중")
    
    if 'tistory_info_content' not in st.session_state: 
        st.session_state.tistory_info_content = ""
    if 'tistory_info_display' not in st.session_state: 
        st.session_state.tistory_info_display = ""
    
    keyword = st.text_input("💎 키워드", key="tistory_info_kw", placeholder="예: 연예인 은퇴 선언")
    
    
    if st.button("🚀 고품질 콘텐츠 생성", key="tistory_info_btn"):
        if not keyword:
            st.warning("⚠️ 키워드를 입력해주세요.")
        else:
            with st.spinner('전문가 페르소나 접속 중...'):
                try:
                    persona = random.choice(TISTORY_INFO_PERSONAS)
                    facts = hunt_realtime_info(keyword)
                    prompt = generate_tistory_info_prompt(keyword, facts, persona)
                    
                    st.info(f"🎭 페르소나: {persona['role']}")
                    
                    response = model.generate_content(prompt)
                    raw_text = response.text
                    
                    json_match = re.search(r'\{.*\}', raw_text, re.DOTALL)
                    if json_match:
                        data = json.loads(json_match.group())
                        title = data.get('title', f'{keyword} 완전 분석')
                        content = data.get('content', '')
                        
                        # 소제목 스타일 적용
                        def replace_h3(match):
                            style = get_premium_style()
                            return f"<br><h3 style='{style}'>{match.group(1)}</h3>"
                        
                        content = re.sub(r'\[H3\](.*?)\[/H3\]', replace_h3, content)
                        
                        final = f"""<div style="font-family: 'Noto Sans KR', sans-serif; font-size: 16px; line-height: 1.8; color: #333; max-width: 800px; margin: auto;">
<h1 style="font-size: 32px; font-weight: bold; color: #222; margin: 30px 0; text-align: center;">{title}</h1>

<div style="padding: 15px; background: #f1f3f5; border-radius: 8px; margin: 20px 0;">
<b style="color: #495057;">💡 핵심 요약:</b> {keyword}에 대한 심층 분석
</div>

{content}

<div style="margin-top: 40px; padding-top: 20px; border-top: 2px solid #dee2e6; color: #6c757d; font-size: 14px;">{data.get('hashtags', '')}</div>
</div>"""
                        
                        st.session_state.tistory_info_content = final
                        st.session_state.tistory_info_display = clean_all_tags(final)
                    else:
                        st.error("JSON 형식을 찾을 수 없습니다.")
                except Exception as e:
                    st.error(f"오류: {e}")
    
    if st.session_state.tistory_info_display:
        st.divider()
        
        # 미리보기 항상 표시
        st.subheader("🖥️ 미리보기")
        st.components.v1.html(st.session_state.tistory_info_content, height=800, scrolling=True)
        
        st.divider()
        
        # HTML 코드도 항상 표시
        st.subheader("📋 HTML 코드")
        st.text_area("복사하세요", value=st.session_state.tistory_info_content, height=300, key="tistory_info_html_area")
        
        st.info("💡 팁: 위 HTML 코드를 복사해서 티스토리 HTML 모드에 붙여넣으세요!")

# ==========================================
# 6. 티스토리 수익형 (t정보.py 완전 이식)
# ==========================================

BUTTON_PHRASES = [
    "👉 실시간 혜택 확인하기", "👉 역대급 특가 정보 보기", "👉 품절 전 재고 선점하기",
    "👉 공식몰 프로모션 확인", "👉 오늘만 진행되는 할인 보기", "👉 사용자 리얼 후기 확인",
    "👉 놓치면 후회할 최저가 좌표", "👉 지금 바로 상세 정보 확인", "👉 혜택 적용된 최종가 보기"
]

T_CTA_PHRASES = [
    "⚠️ 재고 비상! 지금 망설이면 품절각",
    "⏳ 오늘만 이 가격! 내일이면 정상가",
    "🚨 긴급 물량 확보! 소량 입고",
    "⚡ 품절 대란템, 보일 때 잡으세요",
    "💡 삶의 질 수직 상승! 강력 추천",
    "✨ 고민은 배송만 늦출 뿐",
    "💯 후기가 증명합니다",
    "💰 이 스펙에 이 가격? 사장님 미쳤어요",
    "👀 이 가격은 여기뿐! 최저가 좌표",
    "🔥 맘카페 난리 난 바로 그 제품"
]

CSS_STYLE = """
<style>
.blink-border {
  background: #fbf0f6;
  border: 3px solid red;
  border-radius: 11px;
  padding: 18px 16px;
  margin: 25px 0;
  font-family: 'Nanum Gothic', sans-serif;
  line-height: 1.5;
  animation: border-blink 0.5s steps(1, end) infinite;
}
.banner-wrapper {
  display: inline-block;
  border: 3px solid red;
  padding: 5px;
  margin: 20px 0;
  animation: border-blink 0.5s steps(1, end) infinite;
}
@keyframes border-blink {
  0%   { border-color: red; }
  50%  { border-color: transparent; }
  100% { border-color: red; }
}
.highlight-text {
  font-weight: 900;
  font-size: 1.2em;
}
.animate-text {
  display: inline-block;
  animation: pulseText 1s infinite alternate;
}
@keyframes pulseText {
  from { color: #000; transform: scale(1); }
  to { color: #e60000; transform: scale(1.1); }
}
.animate-emoji {
  display: inline-block;
  animation: bounceEmoji 0.8s infinite alternate;
  font-size: 1.4em;
  margin-right: 5px;
}
@keyframes bounceEmoji {
  from { transform: scale(1); }
  to { transform: scale(1.6); }
}
.highlight-link {
  color: #1a3d7c;
  font-weight: bold;
  text-decoration: underline;
  font-size: 1.05em;
}
</style>
"""

def get_random_h3_style_tistory(text):
    """티스토리 수익형 소제목"""
    color = "#{:06x}".format(random.randint(0, 0x777777))
    styles = [
        f'border-left: 10px solid {color}; border-bottom: 2px solid {color}; padding: 5px 15px; margin: 40px 0 15px 0; font-weight: bold; font-size: 1.3em; display: block;',
        f'background-color: {color}; color: white; padding: 10px 18px; margin: 40px 0 15px 0; font-weight: bold; border-radius: 5px; display: block;',
        f'border-bottom: 5px double {color}; padding-bottom: 8px; margin: 40px 0 15px 0; font-weight: bold; font-size: 1.4em; display: block;',
        f'border: 2px solid {color}; padding: 15px; border-left: 10px solid {color}; border-radius: 0 10px 10px 0; background: #ffffff; margin: 40px 0 15px 0; font-weight: bold; display: block;'
    ]
    return f'<br><h3 style="{random.choice(styles)}">{text}</h3>'

def create_compact_cta_tistory(product_name, product_url):
    """티스토리 애니메이션 CTA"""
    phrase = random.choice(T_CTA_PHRASES)
    full_btn_text = random.choice(BUTTON_PHRASES)
    emoji = full_btn_text[0]
    btn_text_only = full_btn_text[1:].strip()
    
    return f"""
<div class="blink-border">
    <span class="highlight-text animate-text">{phrase}</span><br />
    <div style="margin-top: 12px;">
        <span class="animate-emoji">{emoji}</span>
        <a class="highlight-link" href="{product_url}" target="_blank" rel="noopener">
            {btn_text_only} ({product_name})
        </a>
    </div>
</div>
"""

def generate_tistory_profit_prompt(keyword, product_name, facts):
    """티스토리 수익형 프롬프트"""
    return f"""
당신은 구매 심리 마케팅 전문가입니다.

[절대 준수]
1. 자기소개 절대 금지 ("안녕하세요", "저는", "~입니다" 금지)
2. 제목: {product_name} 포함, 20자 내외, 다양한 후킹
   다음 중 하나 사용:
   - "{product_name} 샀다가 멘붕 온 이유"
   - "{product_name} 이거 모르면 손해"
   - "{product_name} 진실 알려드립니다"
   - "{product_name} vs 경쟁 제품 비교"
   - "{product_name} 숨겨진 비밀"
   - "{product_name} 지금 안 사면 후회"
3. 첫 줄부터 팩트로 공격 (자기소개 없이!)
4. **5개 소제목 반드시 <h3>태그 사용!**
   예: <h3>첫 번째 소제목</h3>
       <h3>두 번째 소제목</h3>
5. 중간 [CTA_1], 끝 [CTA_2]
6. 이미지 금지

[정보]
- 키워드: {keyword}
- 제품: {product_name}
- 뉴스: {facts}

[글자수] 2500자 이상

[JSON 응답]
{{
    "title": "강력한 후킹 제목 20자",
    "content": "본문",
    "hashtags": "7개"
}}

JSON만 출력하세요.
"""

def render_tistory_profit():
    """티스토리 수익형 UI"""
    st.title("🟠 티스토리 수익형 v1.1: 애니메이션 CTA")
    
    if 'tistory_profit_content' not in st.session_state:
        st.session_state.tistory_profit_content = ""
    
    c1, c2, c3 = st.columns(3)
    with c1: 
        keyword = st.text_input("💎 키워드", key="tp_kw", placeholder="예: 아이패드 프로")
    with c2: 
        product_name = st.text_input("📦 상품명", key="tp_prod", placeholder="예: 아이패드 프로 M4")
    with c3: 
        product_url = st.text_input("🔗 제휴 URL", key="tp_url", placeholder="https://...")
    
    banner_tag = st.text_area("🖼️ 외부태그 (선택)", key="tp_banner", placeholder="쿠팡 배너 등 HTML 태그")
    
    # 입력 변경 감지 - 자동 초기화
    current_input_tp = f"{keyword}_{product_name}_{product_url}"
    if 'tistory_profit_last_input' not in st.session_state:
        st.session_state.tistory_profit_last_input = ""
    
    if current_input_tp != st.session_state.tistory_profit_last_input:
        st.session_state.tistory_profit_content = ""
        st.session_state.tistory_profit_last_input = current_input_tp
    
    if st.button("🚀 수익형 원고 생성", key="tp_btn"):
        if not keyword or not product_name or not product_url:
            st.error("🚨 필수 항목을 입력하세요.")
        else:
            with st.spinner('구매 심리 자극 중...'):
                try:
                    facts = hunt_realtime_info(keyword)
                    prompt = generate_tistory_profit_prompt(keyword, product_name, facts)
                    
                    response = model.generate_content(prompt)
                    data = json.loads(re.search(r'\{.*\}', response.text, re.DOTALL).group())
                    
                    title = data['title']
                    content = data['content']
                    
                    disclosure = get_ftc_text(product_url)
                    
                    # 소제목 스타일링
                    h3_matches = re.findall(r'<h3>(.*?)</h3>', content)
                    styled_h3_list = []
                    for match in h3_matches:
                        styled_h3 = get_random_h3_style_tistory(match)
                        styled_h3_list.append(styled_h3)
                        content = content.replace(f"<h3>{match}</h3>", styled_h3, 1)
                    
                    # 외부태그 삽입
                    if banner_tag and styled_h3_list:
                        banner_html = f'<div style="text-align:center;"><div class="banner-wrapper">{banner_tag}</div></div>'
                        content = content.replace(styled_h3_list[0], banner_html + styled_h3_list[0], 1)
                    
                    # CTA 치환
                    content = content.replace("[CTA_1]", create_compact_cta_tistory(product_name, product_url))
                    content = content.replace("[CTA_2]", create_compact_cta_tistory(product_name, product_url))
                    
                    final = f"""
<div style='font-family: sans-serif; line-height: 2; color: #333; max-width: 800px; margin: auto; word-break: keep-all;'>
    {CSS_STYLE}
    <p style='color: #888; font-size: 13px;'>{disclosure}</p><hr>
    <h1 style='font-size: 1.7em; line-height: 1.4; color: #000; margin-bottom: 20px;'>{title}</h1>
    {content}
    <br><div style='color: #aaa; margin-top: 40px; border-top: 1px solid #eee; padding-top: 20px;'>{data['hashtags']}</div>
</div>
"""
                    st.session_state.tistory_profit_content = final
                    
                except Exception as e: 
                    st.error(f"오류: {e}")
    
    if st.session_state.tistory_profit_content:
        st.divider()
        
        # 미리보기 항상 표시
        st.subheader("🖥️ 미리보기")
        st.components.v1.html(st.session_state.tistory_profit_content, height=800, scrolling=True)
        
        st.divider()
        
        # HTML 코드도 항상 표시
        st.subheader("📋 HTML 코드")
        st.text_area("복사하세요", value=st.session_state.tistory_profit_content, height=300, key="tistory_profit_html_area")
        
        st.info("💡 팁: 위 HTML 코드를 복사해서 티스토리 HTML 모드에 붙여넣으세요!")

# ==========================================
# 7. 메인 UI
# ==========================================

st.set_page_config(page_title="GHOST HUB v1.1", layout="wide", initial_sidebar_state="expanded")

st.sidebar.title("💀 GHOST HUB v1.1")
st.sidebar.markdown("---")

mode = st.sidebar.radio(
    "모드 선택",
    [
        "🟢 네이버 수익형 (FOMO)",
        "🟢 네이버 정보성 (형태다양화)",
        "🟠 티스토리 정보성 (주제집중)",
        "🟠 티스토리 수익형 (애니메이션)"
    ],
    index=0
)

st.sidebar.markdown("---")
st.sidebar.markdown("""
### ✨ v1.1 업데이트

**네이버 수익형**
- CTA 8가지 후킹 랜덤
- 마크다운 완전 제거
- 제목 강력한 후킹

**네이버 정보성**
- 형태 5가지 랜덤
- 배경색 제거
- Unsplash 이미지 5장

**티스토리 정보성**
- 디자인 스킬 강화
- 주제 이탈 방지
- 미리보기/HTML 선택

**티스토리 수익형**
- 완전 구현
- 외부태그 지원
- 미리보기/HTML 선택
""")

# 모드에 따라 렌더링
if mode == "🟢 네이버 수익형 (FOMO)":
    render_naver_profit()
elif mode == "🟢 네이버 정보성 (형태다양화)":
    render_naver_info()
elif mode == "🟠 티스토리 정보성 (주제집중)":
    render_tistory_info()
else:
    render_tistory_profit()
