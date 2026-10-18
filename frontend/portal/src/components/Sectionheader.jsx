export default function Sectionheader({
  eyebrow,
  title,
  accent = false,
  level = 2,
  centered = false,
}) {
  const Heading = level === 1 ? "h1" : "h2";
  const lineColor = accent ? "border-emerald-400" : "border-blue-400";
  const eyebrowColor = accent ? "text-emerald-300" : "text-blue-300";

  return (
    <div className={centered ? "text-center" : undefined}>
      {eyebrow && (
        <div
          className={`mb-3 flex items-center gap-3 ${
            centered ? "justify-center" : ""
          }`}
        >
          <span
            aria-hidden="true"
            className={`h-px w-8 border-t ${lineColor}`}
          />
          <span
            className={`text-xs font-bold uppercase tracking-[0.24em] ${eyebrowColor}`}
          >
            {eyebrow}
          </span>
        </div>
      )}
      <Heading
        className={`text-3xl font-black uppercase leading-tight tracking-tight sm:text-4xl ${
          accent ? "text-slate-900" : "text-white"
        }`}
      >
        {title}
      </Heading>
    </div>
  );
}
