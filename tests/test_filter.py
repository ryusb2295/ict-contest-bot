"""Unit tests for eligibility and major relevance filters."""
import unittest
from datetime import date

from src.filter import filter_contest, is_eligible_student, is_not_expired, is_relevant_major
from src.models import Contest


class TestFilter(unittest.TestCase):
    def test_is_relevant_major_positive(self):
        self.assertTrue(is_relevant_major("2026 대한민국 AI 해커톤 경진대회"))
        self.assertTrue(is_relevant_major("대학생 빅데이터 분석 챌린지"))
        self.assertTrue(is_relevant_major("임베디드 IoT 로봇 SW 개발 경연"))
        self.assertTrue(is_relevant_major("클라우드 기반 웹/앱 서비스 개발 공모전"))
        self.assertTrue(is_relevant_major("사이버 보안 해킹 방어대회 (CTF)"))
        self.assertTrue(is_relevant_major("사회보장 데이터를 활용한 AI 혁신 아이디어 경진대회"))
        self.assertTrue(is_relevant_major("임베디드 SW 자유공모 경진대회"))
        self.assertTrue(is_relevant_major("AI Matter 경진대회"))
        self.assertTrue(is_relevant_major("제주 AI Agent 개발 챌린지"))
        self.assertTrue(is_relevant_major("LLM 모델 개발 공모전"))
        self.assertTrue(is_relevant_major("블록체인 보안 기술 경진대회"))

    def test_is_relevant_major_negative(self):
        self.assertFalse(is_relevant_major("제3회 청소년 백일장 시 수필 공모전"))
        self.assertFalse(is_relevant_major("지역 캐릭터 로고 디자인 공모전"))
        self.assertFalse(is_relevant_major("시민 참여 숏폼 브이로그 영상 공모전"))
        self.assertFalse(is_relevant_major("전국 노래자랑 및 댄스 경연대회"))
        # Verify that generic words like "Asian" do not trigger AI
        self.assertFalse(is_relevant_major("7th Da-Ho Award Asian International Short Film Competition"))
        self.assertFalse(is_relevant_major("제천시장배 전국 e-스포츠 대회", "게임/소프트웨어"))
        self.assertFalse(is_relevant_major("AI 광고 제작 공모전", "웹/모바일/IT"))
        self.assertFalse(is_relevant_major("AI 영상 공모전", "웹/모바일/IT"))
        self.assertFalse(is_relevant_major("AI 달인의 꿀팁 챌린지 시즌4"))
        self.assertFalse(is_relevant_major("AI 포스터 디자인 챌린지"))
        self.assertFalse(is_relevant_major("AI 창조공모대전", "웹/모바일/IT"))

    def test_is_eligible_student_positive(self):
        self.assertTrue(is_eligible_student("전국 대학생 및 대학원생"))
        self.assertTrue(is_eligible_student("누구나 참여 가능 (제한 없음)"))
        self.assertTrue(is_eligible_student("대한민국 국민 누구나(거주지 제한없음)"))
        self.assertTrue(is_eligible_student("제한없음"))
        self.assertTrue(is_eligible_student("전 국민 참여 가능"))
        self.assertTrue(is_eligible_student("국내 거주 대학생(학부생)"))
        self.assertTrue(is_eligible_student("일반인, 청년, 학생"))
        self.assertTrue(is_eligible_student("청년 대상"))
        self.assertTrue(is_eligible_student("일반인 참가 가능"))
        self.assertFalse(is_eligible_student("미확인 / 상세 공고 참조"))

    def test_is_eligible_student_negative(self):
        self.assertFalse(is_eligible_student(Contest.create(title="AI 개발 대회", url="https://example.com").target))
        self.assertFalse(is_eligible_student("초등학생 전용"))
        self.assertFalse(is_eligible_student("중학생만 참가 가능"))
        self.assertFalse(is_eligible_student("만 65세 시니어 전용"))

    def test_is_not_expired(self):
        today = date(2026, 11, 18)
        self.assertTrue(is_not_expired("2026-11-25", today=today))
        self.assertTrue(is_not_expired("2026-11-18", today=today))
        self.assertFalse(is_not_expired("2026-11-17", today=today))

    def test_filter_contest_full_pipeline(self):
        today = date(2026, 11, 18)

        # 1. Valid contest
        valid, reason = filter_contest(
            title="2026 전국 대학생 생성형 AI 서비스 개발 해커톤",
            target="전국 대학교 재학생 및 휴학생",
            category="인공지능, SW",
            apply_end="2026-12-05",
            today=today,
        )
        self.assertTrue(valid)

        open_to_all, _ = filter_contest(
            title="2026 대구 로컬AI그라운드 - 지역문제 해결형 AI활용 경진대회",
            target="대한민국 국민 누구나(거주지 제한없음)",
            apply_end="2026-11-30",
            today=today,
        )
        self.assertTrue(open_to_all)

        # 2. Expired contest
        expired, reason = filter_contest(
            title="2026 AI 해커톤",
            target="대학생",
            category="AI",
            apply_end="2026-11-10",
            today=today,
        )
        self.assertFalse(expired)
        self.assertIn("마감일 경과", reason)

        # 3. Non-target major
        irrelevant, reason = filter_contest(
            title="제2회 아름다운 풍경 사진 공모전",
            target="대학생",
            category="사진",
            apply_end="2026-12-05",
            today=today,
        )
        self.assertFalse(irrelevant)
        self.assertIn("관련 분야 아님", reason)

        # 4. Ineligible student
        ineligible, reason = filter_contest(
            title="어린이 코딩 로봇 경진대회",
            target="초등학생 전용",
            category="로봇 코딩",
            apply_end="2026-12-05",
            today=today,
        )
        self.assertFalse(ineligible)
        self.assertIn("대학생 참가 대상 아님", reason)


if __name__ == "__main__":
    unittest.main()
