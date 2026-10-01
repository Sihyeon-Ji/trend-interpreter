/* 초안 5의 화면을 앱 안에서 창 가득 띄운다. 화면은 자기 글꼴·스타일·라우팅(#해시)을 가진 별도 문서라 iframe 으로 가둔다. */
export function PrototypeFrame({ src, title }: { src: string; title: string }) {
  return <iframe src={src} title={title} className="fixed inset-0 h-dvh w-screen border-0 bg-white" />;
}
