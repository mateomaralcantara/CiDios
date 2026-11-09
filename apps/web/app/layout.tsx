import type { Metadata, Viewport } from "next";
import "./globals.css";
import { AuthProvider } from "@/lib/auth";
import { Nav } from "@/components/Nav";

export const metadata: Metadata = {
  title: { default: "Ciencia de Dios", template: "%s · Ciencia de Dios" },
  description: "Enciclopedia universal inteligente: la evidencia antes que la conclusión.",
  manifest: "/manifest.webmanifest",
  icons: { icon: "/icon.svg" },
};
export const viewport: Viewport = { themeColor: "#7c2d12", width: "device-width", initialScale: 1 };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="es">
      <body className="min-h-screen">
        <AuthProvider>
          <a href="#main" className="sr-only focus:not-sr-only ui p-2">Saltar al contenido</a>
          <Nav />
          <main id="main" className="mx-auto max-w-6xl px-4 pb-24 pt-6">{children}</main>
          <footer className="ui muted mx-auto max-w-6xl px-4 pb-10 text-xs">
            Ciencia de Dios · HARNESS SUPRA · Evidence Engine · Experience OS — Principio: la evidencia antes que la conclusión.
          </footer>
        </AuthProvider>
        <script dangerouslySetInnerHTML={{ __html: `if('serviceWorker' in navigator){navigator.serviceWorker.register('/sw.js').catch(()=>{})}` }} />
      </body>
    </html>
  );
}
