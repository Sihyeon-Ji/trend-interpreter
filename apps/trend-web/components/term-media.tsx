"use client";

import type { TermMedia } from "@/lib/types";
import { t, type Locale } from "@/lib/i18n";

/* 표제어의 대표 그림·영상. 파일을 우리가 보관하지 않는다 —
   그림은 위키미디어 공용의 자유 라이선스만 오고 출처·라이선스를 함께 적는다.
   영상은 유튜브 공식 플레이어(youtube-nocookie)로 끼운다. */

function youtubeId(url: string): string | null {
  const m = /(?:v=|shorts\/|youtu\.be\/)([A-Za-z0-9_-]{6,20})/.exec(url);
  return m ? m[1] : null;
}

export function TermMediaBlock({ media, name, locale }: { media: TermMedia[]; name: string; locale: Locale }) {
  const image = media.find((x) => x.kind === "image");
  const video = media.find((x) => x.kind === "video");
  const vid = video ? youtubeId(video.url) : null;
  if (!image && !vid) return null;

  return (
    <div className="space-y-3">
      {image && (
        <figure className="space-y-1">
          {/* next/image 로 감싸지 않는 것은 위키미디어 도메인을 이미지 설정에 열지 않기 위해서다. */}
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={image.url} alt={name} className="max-h-[320px] rounded-lg border border-hairline object-contain" />
          <figcaption className="text-[12px] text-steel">
            {t(locale, "card_media_src")}:{" "}
            <a href={image.page_url} target="_blank" rel="noreferrer" className="text-link-blue hover:underline">
              Wikimedia Commons
            </a>
            {image.license && ` · ${image.license}`}
            {image.attribution && ` · ${image.attribution}`}
          </figcaption>
        </figure>
      )}
      {vid && (
        <figure className="space-y-1">
          <div className="aspect-video w-full max-w-[420px] overflow-hidden rounded-lg border border-hairline">
            <iframe
              src={`https://www.youtube-nocookie.com/embed/${vid}`}
              title={video?.title || name}
              allow="accelerometer; clipboard-write; encrypted-media; picture-in-picture"
              allowFullScreen
              className="h-full w-full"
            />
          </div>
          {video?.title && <figcaption className="text-[12px] text-steel">{video.title}</figcaption>}
        </figure>
      )}
    </div>
  );
}
