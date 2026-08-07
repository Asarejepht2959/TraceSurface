
import { cn } from "@/lib/utils";

export function Toast({ message }: { message: string }) {
  return <div className={cn("toast", message && "show")}>{message}</div>;
}
