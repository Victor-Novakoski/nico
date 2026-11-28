import type { ReactNode } from "react";
import type { DraftSpan } from "../api";

const FIELDS: Record<string, { color: string; label: string }> = {
  amount_cents: { color: "var(--valor)", label: "Valor" },
  description: { color: "var(--oque)", label: "O quê" },
  method_id: { color: "var(--meio)", label: "Meio" },
  installments: { color: "var(--parcelas)", label: "Parcelas" },
};

type Props = { phrase: string; spans?: DraftSpan[] };

export function PhraseHighlight({ phrase, spans = [] }: Props) {
  const valid = [...spans]
    .filter(
      (s) =>
        s.field in FIELDS &&
        s.start >= 0 &&
        s.start < s.end &&
        s.end <= phrase.length,
    )
    .sort((a, b) => a.start - b.start);

  const parts: ReactNode[] = [];
  let pos = 0;
  for (const s of valid) {
    if (s.start < pos) continue; // sobrepõe o anterior
    if (s.start > pos) parts.push(phrase.slice(pos, s.start));
    parts.push(
      <span
        key={`${s.field}-${s.start}`}
        data-field={s.field}
        className="underline decoration-2 underline-offset-4"
        style={{ color: FIELDS[s.field].color }}
      >
        {phrase.slice(s.start, s.end)}
      </span>,
    );
    pos = s.end;
  }
  if (pos < phrase.length) parts.push(phrase.slice(pos));

  return (
    <div>
      <p className="text-base leading-relaxed">{parts}</p>
      <ul className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-xs">
        {Object.values(FIELDS).map((f) => (
          <li key={f.label} className="flex items-center gap-1">
            <span
              aria-hidden="true"
              className="inline-block h-0.5 w-3"
              style={{ backgroundColor: f.color }}
            />
            {f.label}
          </li>
        ))}
      </ul>
    </div>
  );
}
