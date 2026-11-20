"use client";
export default function ChoiceChips({
  label,
  options,
  selected,
  onChoose,
  disabled = false,
}: {
  label: string;
  options: string[];
  selected: string[];
  onChoose: (value: string) => void;
  disabled?: boolean;
}) {
  return (
    <div className="choice-chips" role="group" aria-label={label}>
      {options.map((option) => (
        <button
          key={option}
          type="button"
          className="secondary"
          aria-pressed={selected.includes(option)}
          disabled={disabled}
          onClick={() => onChoose(option)}
        >
          {option}
        </button>
      ))}
    </div>
  );
}
export const interestChoices = [
  "Basketball",
  "College life",
  "Fitness",
  "Fashion",
  "Gaming",
  "Music",
  "Comedy",
  "Travel",
];
export const audienceChoices = [
  "People with similar interests",
  "College students",
  "Sports fans",
  "People exploring new hobbies",
];
export const styleChoices = ["Casual", "Funny", "Friendly", "Inspiring"];
