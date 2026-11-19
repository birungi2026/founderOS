"use client";
import { useId, useState } from "react";
type Kind = "skills" | "topics" | "style" | "audience";
const guides = {
  skills: {
    title: "Find the skills worth sharing",
    prompts: [
      "What do people ask you for help with?",
      "What have you learned through work or life?",
    ],
    examples: ["Building websites", "Keeping customer data safe"],
    help: "You don’t need a qualification. Think about things you can explain or show someone.",
  },
  topics: {
    title: "Choose useful topics",
    prompts: [
      "What could you teach your audience?",
      "What questions does your audience ask?",
    ],
    examples: ["Simple security tips", "How to avoid common website mistakes"],
    help: "Write one topic per line. Start with a few you can talk about comfortably; you can change them later.",
  },
  style: {
    title: "Choose how your posts should feel",
    prompts: ["Anything else about your writing style?"],
    examples: ["Short sentences, real examples and no technical words"],
    help: "Choose the words that sound like you. You can pick more than one.",
  },
  audience: {
    title: "Explain who you help",
    prompts: [
      "Who do you want to help?",
      "What do they struggle with?",
      "How do you help them?",
    ],
    examples: [
      "Small business owners",
      "Keeping their websites safe",
      "Providing simple security tools and practical tips",
    ],
    help: "A few words for each question are enough. Rymu will arrange them into an answer you can edit.",
  },
};
const styles = ["Friendly", "Professional", "Simple", "Funny", "Direct"];
export default function AnswerGuide({
  kind,
  existing,
  onUse,
}: {
  kind: Kind;
  existing: string;
  onUse: (answer: string) => void;
}) {
  const id = useId();
  const [answers, setAnswers] = useState<string[]>([]);
  const [selected, setSelected] = useState<string[]>([]);
  const guide = guides[kind];
  const clean = answers.map((value) => value.trim());
  const list = [
    ...new Set(
      clean
        .flatMap((value) => value.split("\n"))
        .map((value) => value.trim())
        .filter(Boolean),
    ),
  ];
  const preview =
    kind === "audience"
      ? clean[0] && clean[1] && clean[2]
        ? `I help ${clean[0]}. They struggle with ${clean[1]}. I help by ${clean[2]}.`
        : ""
      : kind === "style"
        ? [...selected, clean[0]].filter(Boolean).join(". ")
        : list.slice(0, kind === "topics" ? 5 : 10).join("\n");
  return (
    <details className="answer-guide">
      <summary>Help me answer</summary>
      <div className="answer-guide-body">
        <h4>{guide.title}</h4>
        <p>{guide.help}</p>
        {kind === "style" && (
          <div className="style-choices" aria-label="Writing style choices">
            {styles.map((style) => (
              <button
                type="button"
                key={style}
                aria-pressed={selected.includes(style)}
                className="secondary"
                onClick={() =>
                  setSelected((values) =>
                    values.includes(style)
                      ? values.filter((value) => value !== style)
                      : [...values, style],
                  )
                }
              >
                {style}
              </button>
            ))}
          </div>
        )}
        {guide.prompts.map((prompt, index) => (
          <label key={prompt} htmlFor={`${id}-${index}`}>
            {prompt}
            {(kind === "skills" || kind === "topics") && index === 1
              ? " (optional)"
              : ""}
            <textarea
              id={`${id}-${index}`}
              aria-label={prompt}
              rows={2}
              maxLength={300}
              value={answers[index] || ""}
              placeholder={`For example: ${guide.examples[index]}`}
              onChange={(event) =>
                setAnswers((values) => {
                  const next = [...values];
                  next[index] = event.target.value;
                  return next;
                })
              }
            />
          </label>
        ))}
        <div className="answer-preview">
          <strong>Your draft answer</strong>
          <p>
            {preview ||
              (kind === "audience"
                ? "Answer the three questions above to see your draft."
                : "Add your ideas above to see your draft.")}
          </p>
        </div>
        <button
          type="button"
          disabled={!preview}
          onClick={() => onUse(preview)}
        >
          {existing.trim()
            ? "Replace my answer with this draft"
            : "Use this draft answer"}
        </button>
        <small>
          This guide uses only what you enter. It won’t save or approve your
          profile. You can edit the answer after adding it.
        </small>
      </div>
    </details>
  );
}
