import { type ClassValue, clsx } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatCurrency(amount: number): string {
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
  }).format(amount)
}

export function formatPercent(value: number): string {
  return new Intl.NumberFormat("en-IN", {
    style: "percent",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value)
}

export function formatNumber(value: number): string {
  return new Intl.NumberFormat("en-IN").format(value)
}

export function getStatusColor(status: string): string {
  switch (status) {
    case "active":
      return "text-green-600 bg-green-100 dark:text-green-400 dark:bg-green-900"
    case "inactive":
      return "text-red-600 bg-red-100 dark:text-red-400 dark:bg-red-900"
    case "warning":
      return "text-yellow-600 bg-yellow-100 dark:text-yellow-400 dark:bg-yellow-900"
    default:
      return "text-gray-600 bg-gray-100 dark:text-gray-400 dark:bg-gray-900"
  }
}

export function getPnlColor(pnl: number): string {
  if (pnl > 0) return "text-green-600"
  if (pnl < 0) return "text-red-600"
  return "text-gray-600"
} 