import { cn } from "@/lib/utils";

/**
 * An answer arriving word by word: each word rises out of a blur, the whole reveal taking about
 * 0.9 s at most. The words stay plain inline text, so assistive tech reads the finished answer,
 * and the global reduced-motion rule shows it at once.
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
  if (!animate) {
    return (
      <p lang={lang} className={cn("whitespace-pre-line", className)}>
        {text}
      </p>
    );
  }
  const parts = text.split(/(\s+)/);
  const words = parts.filter((part) => part.trim()).length;
  const step = Math.min(28, 700 / Math.max(1, words));
  let word = 0;
  return (
    <p lang={lang} className={cn("whitespace-pre-line", className)}>
      {parts.map((part, index) =>
        part.trim() ? (
          <span key={index} className="word-in" style={{ animationDelay: `${Math.round(word++ * step)}ms` }}>
            {part}
          </span>
        ) : (
          part
        ),
      )}
    </p>
  );
}
