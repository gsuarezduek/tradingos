"use client";

import { Suspense, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";

function TextField({
  label,
  value,
  onChange,
  type = "text",
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  type?: string;
}) {
  return (
    <label className="flex flex-col gap-1.5">
      <span className="text-xs font-medium text-muted">{label}</span>
      <input
        type={type}
        value={value}
        autoComplete={type === "password" ? "current-password" : "email"}
        onChange={(e) => onChange(e.target.value)}
        className="rounded-lg border border-border bg-surface px-3 py-2 text-sm text-ink"
      />
    </label>
  );
}

function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    setLoading(true);
    setError(null);

    try {
      const response = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });

      const data = await response.json();
      if (!response.ok) {
        setError(typeof data.detail === "string" ? data.detail : "No se pudo iniciar sesión.");
        return;
      }

      router.push(searchParams.get("next") ?? "/conexiones");
      router.refresh();
    } catch {
      setError("No se pudo conectar con la API. Probá de nuevo.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mx-auto flex max-w-sm flex-col gap-8 pt-16">
      <div>
        <h1 className="text-2xl font-bold text-ink">Iniciar sesión</h1>
        <p className="text-sm text-muted">Entrá para ver tus conexiones guardadas.</p>
      </div>

      <div className="flex flex-col gap-4 rounded-3xl bg-panel p-8">
        <TextField label="Email" value={email} onChange={setEmail} type="email" />
        <TextField label="Contraseña" value={password} onChange={setPassword} type="password" />

        <button
          onClick={submit}
          disabled={loading || !email || !password}
          className="mt-2 rounded-xl bg-ink px-5 py-2.5 text-sm font-semibold text-white disabled:opacity-50"
        >
          {loading ? "Entrando…" : "Entrar"}
        </button>

        {error && <p className="text-sm text-muted">{error}</p>}
      </div>

      <p className="text-center text-sm text-muted">
        ¿No tenés cuenta?{" "}
        <Link href="/register" className="font-semibold text-ink">
          Registrate
        </Link>
      </p>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense>
      <LoginForm />
    </Suspense>
  );
}
