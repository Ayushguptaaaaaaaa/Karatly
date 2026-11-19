import {
  IconAdjustments,
  IconArrowBackUp,
  IconArrowForwardUp,
  IconCircleCheck,
  IconAlertCircle,
  IconCircleX,
  IconFlame,
  IconPackage,
  IconShoppingBag,
  IconSparkles,
  IconTrendingDown,
  IconTrendingUp,
  IconTruckDelivery,
  IconZzz,
  type Icon,
} from "@tabler/icons-react";
import type { DemandClass, MovementType, StockStatus } from "../api/types";

export const STATUS_META: Record<StockStatus, { label: string; color: string; icon: Icon; hex: string }> = {
  IN: { label: "In stock", color: "teal", icon: IconCircleCheck, hex: "#2b8a3e" },
  LOW: { label: "Low", color: "orange", icon: IconAlertCircle, hex: "#e67700" },
  OUT: { label: "Sold out", color: "red", icon: IconCircleX, hex: "#c92a2a" },
  DEAD: { label: "Not selling", color: "gray", icon: IconZzz, hex: "#5c5f66" },
};

export const DEMAND_META: Record<DemandClass, { label: string; color: string; icon: Icon }> = {
  HIGH: { label: "High demand", color: "orange", icon: IconFlame },
  STEADY: { label: "Steady", color: "blue", icon: IconTrendingUp },
  LOW: { label: "Low demand", color: "gray", icon: IconTrendingDown },
  DEAD: { label: "Not selling", color: "dark", icon: IconZzz },
  NEW: { label: "New", color: "cyan", icon: IconSparkles },
};

export const MOVEMENT_META: Record<MovementType, { label: string; short: string; icon: Icon; dir: "IN" | "OUT"; color: string }> = {
  OPENING: { label: "Opening stock", short: "Opening", icon: IconPackage, dir: "IN", color: "gray" },
  PURCHASE: { label: "New stock received", short: "New stock", icon: IconTruckDelivery, dir: "IN", color: "teal" },
  CUSTOMER_RETURN: { label: "Customer return", short: "Return", icon: IconArrowBackUp, dir: "IN", color: "blue" },
  ADJUSTMENT_IN: { label: "Correction (+)", short: "Correction +", icon: IconAdjustments, dir: "IN", color: "grape" },
  SALE: { label: "Sale", short: "Sale", icon: IconShoppingBag, dir: "OUT", color: "red" },
  SUPPLIER_RETURN: { label: "Return to supplier", short: "To supplier", icon: IconArrowForwardUp, dir: "OUT", color: "orange" },
  ADJUSTMENT_OUT: { label: "Correction (−)", short: "Correction −", icon: IconAdjustments, dir: "OUT", color: "grape" },
};

export const IN_REASONS: MovementType[] = ["PURCHASE", "CUSTOMER_RETURN", "ADJUSTMENT_IN"];
export const OUT_REASONS: MovementType[] = ["SALE", "SUPPLIER_RETURN", "ADJUSTMENT_OUT"];

export const CATEGORY_COLORS = ["gold", "teal", "blue", "grape", "orange", "cyan", "pink", "lime", "indigo", "red"];

export function categoryColor(id: number): string {
  return CATEGORY_COLORS[(Math.max(1, id) - 1) % CATEGORY_COLORS.length];
}

export const PURITY_OPTIONS = ["24K", "22K", "18K", "14K", "925", "950", "Other"];
export const METAL_OPTIONS = [
  { value: "GOLD", label: "Gold" },
  { value: "SILVER", label: "Silver" },
  { value: "PLATINUM", label: "Platinum" },
  { value: "OTHER", label: "Other" },
];

export const QUICK_CATEGORIES: { name: string; icon: string }[] = [
  { name: "Necklaces", icon: "necklace" },
  { name: "Earrings", icon: "earring" },
  { name: "Bangles", icon: "bangle" },
  { name: "Bracelets", icon: "bracelet" },
  { name: "Anklets", icon: "anklet" },
  { name: "Rings", icon: "ring" },
  { name: "Chains", icon: "chain" },
  { name: "Pendants", icon: "pendant" },
];
