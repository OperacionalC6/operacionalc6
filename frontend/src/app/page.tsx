"use client";

import Script from "next/script";
import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { ApiError, loginWithGoogle } from "@/lib/api";
import { GOOGLE_CLIENT_ID } from "@/lib/config";
import { isLoggedIn } from "@/lib/auth";

export default function LoginPage() {
  const router = useRouter();
  const buttonRef = useRef<HTMLDivElement>(null);
  const [scriptReady, setScriptReady] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (isLoggedIn()) {
      router.replace("/dashboard");
    }
  }, [router]);

  useEffect(() => {
    if (!scriptReady || !buttonRef.current || !window.google) return;

    window.google.accounts.id.initialize({
      client_id: GOOGLE_CLIENT_ID,
      callback: async (response) => {
        setError(null);
        try {
          await loginWithGoogle(response.credential);
          router.push("/dashboard");
        } catch (err) {
          setError(err instanceof ApiError ? err.message : "Falha ao entrar.");
        }
      },
    });

    window.google.accounts.id.renderButton(buttonRef.current, {
      theme: "outline",
      size: "large",
      text: "signin_with",
      locale: "pt-BR",
    });
  }, [scriptReady, router]);

  return (
    <>
      <Script
        src="https://accounts.google.com/gsi/client"
        strategy="afterInteractive"
        onReady={() => setScriptReady(true)}
      />
      <div className="flex flex-1 items-center justify-center bg-zinc-50">
        <div className="flex w-full max-w-sm flex-col items-center gap-6 rounded-xl border border-zinc-200 bg-white p-10 shadow-sm">
          <div className="flex flex-col items-center gap-1 text-center">
            <h1 className="text-xl font-semibold text-zinc-900">Operacional C6</h1>
            <p className="text-sm text-zinc-500">
              Painel de comissão e produção do correspondente bancário.
            </p>
          </div>
          <div ref={buttonRef} />
          {error && <p className="text-sm text-red-600">{error}</p>}
          <p className="text-center text-xs text-zinc-400">
            Acesso apenas para e-mails previamente cadastrados por um administrador.
          </p>
        </div>
      </div>
    </>
  );
}
