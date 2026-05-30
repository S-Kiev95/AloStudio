"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useConnectManual } from "@/lib/api/instagram";

const schema = z.object({
  name: z.string().min(1, "Nombre requerido"),
  instagram_id: z.string().min(1, "IG Business Account ID requerido"),
  access_token: z.string().min(1, "Token requerido"),
  login_type: z.enum(["facebook", "instagram"]),
});
type FormInput = z.infer<typeof schema>;

/** Advanced connect: paste a (permanent) token. */
export function ManualConnectForm({ accountId }: { accountId: string }) {
  const [error, setError] = useState<string | null>(null);
  const connect = useConnectManual(accountId);
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<FormInput>({
    resolver: zodResolver(schema),
    defaultValues: { login_type: "facebook" },
  });

  async function onSubmit(values: FormInput) {
    setError(null);
    try {
      await connect.mutateAsync(values);
      reset();
    } catch {
      setError("No se pudo conectar. Revisá el token y el IG id.");
    }
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-3" noValidate>
      {error ? (
        <p role="alert" className="text-sm text-danger">
          {error}
        </p>
      ) : null}
      <div className="space-y-1.5">
        <Label htmlFor="m-name" required>
          Nombre del inbox
        </Label>
        <Input id="m-name" {...register("name")} aria-invalid={!!errors.name} />
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="m-igid" required>
          IG Business Account ID
        </Label>
        <Input
          id="m-igid"
          {...register("instagram_id")}
          aria-invalid={!!errors.instagram_id}
        />
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="m-token" required>
          Page / IG access token
        </Label>
        <Input
          id="m-token"
          type="password"
          {...register("access_token")}
          aria-invalid={!!errors.access_token}
        />
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="m-login">Tipo de conexión</Label>
        <select
          id="m-login"
          {...register("login_type")}
          className="h-11 w-full rounded-md border border-border bg-surface px-3 text-sm text-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <option value="facebook">Facebook Login (permite borrar)</option>
          <option value="instagram">Instagram Login (sin borrado)</option>
        </select>
      </div>
      <Button type="submit" loading={isSubmitting}>
        Conectar con token
      </Button>
    </form>
  );
}
