
import os
from supabase import create_client, Client

# 환경변수에서 Supabase URL과 키를 읽어옴
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("Supabase 환경변수가 설정되지 않았습니다.")

# Supabase 클라이언트 생성
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# 추가로 DB 관련 함수들 정의 가능
# 예: 음성 활동 저장, 조회, 통계 함수 등
