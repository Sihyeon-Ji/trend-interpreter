import type { ApiRequestInit } from "./api-transport";

export type Viewer = { user: string; reviewer: boolean; readOnly?: boolean };

export class ReviewerAccessError extends Error {
  constructor(readonly status: number, message: string) {
    super(message);
  }
}

export function assertReviewer(viewer: Viewer | null): Viewer {
  if (!viewer) throw new ReviewerAccessError(401, "로그인이 필요합니다.");
  if (!viewer.reviewer) throw new ReviewerAccessError(403, "이 계정에는 사전 검수 권한이 없습니다.");
  return viewer;
}

export function createReviewerReader(
  fetcher: (path: string, init: ApiRequestInit) => Promise<Response>,
  viewer: () => Promise<Viewer | null>,
  token: () => string | undefined,
) {
  return async (path: string): Promise<Response> => {
    assertReviewer(await viewer());
    const value = token();
    if (!value) throw new ReviewerAccessError(500, "검수 서버 설정이 빠졌습니다.");
    return fetcher(path, { headers: { "x-frontend-token": value }, cache: "no-store" });
  };
}
