// Thin wrapper around RevenueCat (App Store + Google Play billing).
// The server never trusts what this reports — after a purchase/restore we call
// POST /billing/sync and the server checks RevenueCat itself.

import Constants from 'expo-constants';
import { Platform } from 'react-native';
import Purchases, {
  PACKAGE_TYPE,
  PRODUCT_CATEGORY,
  PURCHASES_ERROR_CODE,
  type PurchasesPackage,
} from 'react-native-purchases';

const extra = (Constants.expoConfig?.extra ?? {}) as Record<string, string | undefined>;
const API_KEY = Platform.select({ ios: extra.revenuecatIosKey, android: extra.revenuecatAndroidKey }) || '';

let configured = false;
let currentUser: string | null = null;

/** Store billing is available (SDK key present for this platform). */
export const storeBillingAvailable = !!API_KEY;

function ensureConfigured() {
  if (!API_KEY) throw new Error('In-app purchases aren’t set up in this build of the app.');
  if (!configured) {
    Purchases.configure({ apiKey: API_KEY });
    configured = true;
  }
}

/** Tie purchases to the Forge account so they follow the user across devices. */
export async function identify(appUserId: string): Promise<void> {
  if (!API_KEY || currentUser === appUserId) return;
  try {
    ensureConfigured();
    await Purchases.logIn(appUserId);
    currentUser = appUserId;
  } catch (e) {
    console.warn('RevenueCat logIn failed', e);
  }
}

export async function forget(): Promise<void> {
  if (!configured || !currentUser) return;
  currentUser = null;
  try {
    await Purchases.logOut();
  } catch {
    // already anonymous
  }
}

export interface Plan {
  pkg: PurchasesPackage;
  title: string;
  price: string;
  detail: string;
  oneTime: boolean;
  /** Higher sorts first */
  rank: number;
}

const PLAN_META: Partial<Record<PACKAGE_TYPE, { title: string; detail: string; rank: number; oneTime?: boolean }>> = {
  [PACKAGE_TYPE.MONTHLY]: { title: 'Monthly', detail: 'per month, cancel anytime', rank: 1 },
  [PACKAGE_TYPE.ANNUAL]: { title: 'Yearly', detail: 'per year, cancel anytime', rank: 3 },
  [PACKAGE_TYPE.LIFETIME]: { title: 'Lifetime', detail: 'one-time purchase', rank: 2, oneTime: true },
};

export async function loadPlans(): Promise<Plan[]> {
  ensureConfigured();
  const offerings = await Purchases.getOfferings();
  const packages = offerings.current?.availablePackages ?? [];
  return packages
    .map((pkg) => {
      const meta = PLAN_META[pkg.packageType];
      const oneTime = meta?.oneTime ?? pkg.product.productCategory === PRODUCT_CATEGORY.NON_SUBSCRIPTION;
      return {
        pkg,
        title: meta?.title ?? pkg.product.title,
        price: pkg.product.priceString,
        detail: meta?.detail ?? (oneTime ? 'one-time purchase' : pkg.product.description),
        oneTime,
        rank: meta?.rank ?? 0,
      };
    })
    .sort((a, b) => b.rank - a.rank);
}

/** Returns false if the user cancelled the store sheet. */
export async function buy(plan: Plan): Promise<boolean> {
  ensureConfigured();
  try {
    await Purchases.purchasePackage(plan.pkg);
    return true;
  } catch (e) {
    const err = e as { code?: string; userCancelled?: boolean | null };
    if (err.code === PURCHASES_ERROR_CODE.PURCHASE_CANCELLED_ERROR || err.userCancelled) return false;
    throw e;
  }
}

export async function restore(): Promise<void> {
  ensureConfigured();
  await Purchases.restorePurchases();
}
