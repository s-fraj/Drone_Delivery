import { useState, type ImgHTMLAttributes } from 'react';

type Props = ImgHTMLAttributes<HTMLImageElement> & { fallback: string };

/** <img> that swaps to a remote fallback if the local asset is missing. */
export function FallbackImg({ fallback, src, ...rest }: Props) {
  const [failed, setFailed] = useState(false);
  return <img {...rest} src={failed ? fallback : src} onError={() => setFailed(true)} />;
}
