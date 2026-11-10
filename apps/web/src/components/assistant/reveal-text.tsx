import { boldSegments } from "@/lib/bold-text";
import { cn } from "@/lib/utils";

/**
 * An answer arriving word by word: each word rises out of a blur, the whole reveal taking about
 * 0.9 s at most. The words stay plain inline text, so assistive tech reads the finished answer,
 * and the global reduced-motion rule shows it at once. WhatsApp-style *bold* shows as bold.
 */
export function RevealText({
  text,
  animate,
  lang,
  className,
}: {
  text: string;
  animate: boolean;
  lang?: string | undefined;
  className?: string | undefined;
}) {
  const segments = boldSegments(text);
  if (!animate) {
    return (
      <p lang={lang} className={cn("whitespace-pre-line", className)}>
        {segments.map((segment, index) =>
          segment.bold ? (
            <strong key={index} className="font-semibold">
              {segment.text}
            </strong>
          ) : (
            segment.text
          ),
        )}
      </p>
    );
  }
  const words = segments.reduce(
    (count, segment) => count + segment.text.split(/\s+/).filter(Boolean).length,
    0,
  );
  const step = Math.min(28, 700 / Math.max(1, words));
  let word = 0;
  return (
    <p lang={lang} className={cn("whitespace-pre-line", className)}>
      {segments.map((segment, index) => {
        const parts = segment.text.split(/(\s+)/).map((part, at) =>
          part.trim() ? (
            <span key={at} className="word-in" style={{ animationDelay: `${Math.round(word++ * step)}ms` }}>
              {part}
            </span>
          ) : (
            part
          ),
        );
        return segment.bold ? (
          <strong key={index} className="font-semibold">
            {parts}
          </strong>
        ) : (
          <span key={index}>{parts}</span>
        );
      })}
    </p>
  );
}
