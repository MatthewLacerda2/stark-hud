import { useTranslation } from "react-i18next";

/** Shown when the backend 404s because the file moved or was deleted. */
export function Missing({ path }: { path: string }) {
  const { t } = useTranslation();
  return (
    <div className="flex size-full flex-col items-center justify-center gap-2 rounded-xl bg-background p-4">
      <span className="text-node text-foreground">{t("media.missing")}</span>
      <span className="max-w-full truncate text-node-sm text-muted-foreground">
        {path}
      </span>
    </div>
  );
}
