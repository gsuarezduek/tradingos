"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

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
        autoComplete={type === "password" ? "new-password" : "email"}
        onChange={(e) => onChange(e.target.value)}
        className="rounded-lg border border-border bg-surface px-3 py-2 text-sm text-ink"
      />
    </label>
  );
}

export default function RegisterPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    setLoading(true);
    setError(null);

    try {
      const response = await fetch("/api/auth/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });

      const data = await response.json();
      if (!response.ok) {
        setError(typeof data.detail === "string" ? data.detail : "No se pudo crear la cuenta.");
        return;
      }

      router.push("/conexiones");
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
        <h1 className="text-2xl font-bold text-ink">Crear cuenta</h1>
        <p className="text-sm text-muted">Para guardar tus conexiones de exchanges.</p>
      </div>

      <div className="flex flex-col gap-4 rounded-3xl bg-panel p-8">
        <TextField label="Email" value={email} onChange={setEmail} type="email" />
        <TextField label="Contraseña" value={password} onChange={setPassword} type="password" />
        <p className="text-xs text-muted">Mínimo 8 caracteres.</p>

        <button
          onClick={submit}
          disabled={loading || !email || !password}
          className="mt-2 rounded-xl bg-ink px-5 py-2.5 text-sm font-semibold text-white disabled:opacity-50"
        >
          {loading ? "Creando cuenta…" : "Crear cuenta"}
        </button>

        {error && <p className="text-sm text-muted">{error}</p>}
      </div>

      <p className="text-center text-sm text-muted">
        ¿Ya tenés cuenta?{" "}
        <Link href="/login" className="font-semibold text-ink">
          Iniciá sesión
        </Link>
      </p>
    </div>
  );
}
