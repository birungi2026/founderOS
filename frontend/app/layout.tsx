import "./style.css";
import "./professional.css";
import "./rymu.css";
export const metadata = {
  title: "Rymu",
  description:
    "Your AI growth employee. Build your brand and reach your next customer.",
  metadataBase: new URL("https://rymu.ai"),
  icons: { icon: "/rymu-mark.png", apple: "/rymu-mark.png" },
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
