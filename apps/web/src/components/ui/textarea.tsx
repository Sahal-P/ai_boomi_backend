import * as React from "react"
import { cn } from "cn"

function Textarea({ className, ...props }: React.ComponentProps<"textarea">) {
  return (
    <textarea
      data-slot="textarea"
      className={cn(
        "field flex field-sizing-content min-h-16 w-full rounded-lg px-3.5 py-2.5 text-base md:text-sm",
        className
      )}
      {...props}
    />
  )
}

export { Textarea }
