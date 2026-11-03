/** 표시 포맷.
 *
 * 숫자는 한국 사용자가 실제로 쓰는 단위(만원/억원)로 줄여 쓴다. "10,000,000원"
 * 보다 "1,000만원" 이 한눈에 들어온다.
 */

export function formatPrize(value: number | null | undefined): string {
  if (!value || value <= 0) return "미확인";
  if (value >= 100_000_000) {
    const eok = value / 100_000_000;
    return `${eok % 1 === 0 ? eok : eok.toFixed(1)}억원`;
  }
  if (value >= 10_000) {
    const man = Math.round(value / 10_000);
    return `${man.toLocaleString("ko-KR")}만원`;
  }
  return `${value.toLocaleString("ko-KR")}원`;
}

export function formatPrizeFull(value: number | null | undefined): string {
  if (!value || value <= 0) return "미확인";
  return `${value.toLocaleString("ko-KR")}원`;
}

export function formatDday(days: number | null | undefined): string {
  if (days === null || days === undefined) return "마감일 미확인";
  if (days < 0) return "마감";
  if (days === 0) return "오늘 마감";
  return `D-${days}`;
}

export function deadlineTone(days: number | null | undefined): "danger" | "warn" | "normal" | "none" {
  if (days === null || days === undefined) return "none";
  if (days < 0) return "none";
  if (days <= 3) return "danger";
  if (days <= 7) return "warn";
  return "normal";
}

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const date = new Date(iso.length === 10 ? `${iso}T00:00:00` : iso);
  if (Number.isNaN(date.getTime())) return iso;
  return new Intl.DateTimeFormat("ko-KR", {
    month: "long",
    day: "numeric",
  }).format(date);
}

export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return new Intl.DateTimeFormat("ko-KR", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

export function formatClock(iso: string | null | undefined): string {
  if (!iso) return "—";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "—";
  return new Intl.DateTimeFormat("ko-KR", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(date);
}

export function relativeTime(iso: string | null | undefined): string {
  if (!iso) return "기록 없음";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "기록 없음";
  const diff = Date.now() - date.getTime();
  const minutes = Math.round(diff / 60_000);
  if (minutes < 1) return "방금";
  if (minutes < 60) return `${minutes}분 전`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours}시간 전`;
  const days = Math.round(hours / 24);
  if (days < 30) return `${days}일 전`;
  return formatDate(iso);
}

export function greeting(): string {
  const hour = new Date().getHours();
  if (hour < 5) return "늦은 밤이네요";
  if (hour < 12) return "좋은 아침입니다";
  if (hour < 18) return "좋은 오후입니다";
  return "좋은 저녁입니다";
}

export const STATUS_LABEL: Record<string, string> = {
  NEW: "신규",
  RECOMMENDED: "추천",
  INTERESTED: "Shortlist",
  ENTERING: "참가 중",
  SUBMITTED: "제출 완료",
  IGNORE: "무시",
  EXPIRED: "마감",
};

export const STAGE_LABEL: Record<string, string> = {
  RESEARCH: "리서치",
  IDEA_DEVELOPMENT: "아이디어 개발",
  PRODUCTION: "제작",
  REVIEW: "검토·보완",
  SUBMITTED: "제출 완료",
};

export const RUN_STATUS_LABEL: Record<string, string> = {
  RUNNING: "실행 중",
  SUCCESS: "성공",
  PARTIAL: "부분 성공",
  FAILED: "실패",
};

export const VERDICT: Record<string, { title: string; note: string }> = {
  S: { title: "최우선 검토", note: "일정을 조정해서라도 확인할 가치가 있습니다." },
  A: { title: "적극 추천", note: "역량과 조건이 잘 맞는 공모전입니다." },
  B: { title: "여유가 있다면", note: "시간이 남을 때 검토해 볼 만합니다." },
  SKIP: { title: "투입 대비 낮음", note: "지금 시간을 쓰기에는 우선순위가 낮습니다." },
};
