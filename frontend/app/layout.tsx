import "./style.css";
export const metadata = {
  title: "FounderOS",
  description: "The AI Growth Employee for Founders",
};
export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
