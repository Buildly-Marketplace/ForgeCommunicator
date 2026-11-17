import Constants from 'expo-constants';
import * as Linking from 'expo-linking';
import { router } from 'expo-router';
import { useEffect, useState } from 'react';
import { ActivityIndicator, Platform, Pressable, ScrollView, View } from 'react-native';

import { Banner, Body, Button, Card, Label, Title, useColors } from '../components/ui';
import * as purchases from '../lib/purchases';
import { useSession } from '../lib/session';

const extra = (Constants.expoConfig?.extra ?? {}) as Record<string, string | undefined>;

const FEATURES = [
  ['☁️', 'Save & sync', 'Your ideas, photos and screenshots on every device'],
  ['✨', 'AI breakdowns', 'Features, issues and tasks with acceptance criteria'],
  ['⏱', 'Estimates', 'Story points plus developer vs. AI-agent hours'],
  ['🚀', 'Send to Labs', 'Straight into your product backlog — or to a coding agent'],
] as const;

function formatDate(iso?: string | null) {
  return iso ? new Date(iso).toLocaleDateString() : '';
}

export default function Paywall() {
  const c = useColors();
  const { token, access, isPro, jottings, refreshAccess } = useSession();
  const [plans, setPlans] = useState<purchases.Plan[] | null>(null);
  const [selected, setSelected] = useState(0);
  const [busy, setBusy] = useState<'buy' | 'restore' | null>(null);
  const [error, setError] = useState<string | null>(null);

  const serverReady = access?.purchases_enabled ?? true;
  const canBuy = !!token && purchases.storeBillingAvailable && serverReady;

  useEffect(() => {
    if (!canBuy || isPro) return;
    purchases
      .loadPlans()
      .then((p) => {
        setPlans(p);
        setSelected(0);
      })
      .catch((e) => setError(e instanceof Error ? e.message : String(e)));
  }, [canBuy, isPro]);

  async function confirmWithServer() {
    // Webhooks can lag a few seconds behind the store; retry briefly
    for (let attempt = 0; attempt < 4; attempt++) {
      const status = await refreshAccess(true);
      if (status?.active) return true;
      await new Promise((r) => setTimeout(r, 1500 * (attempt + 1)));
    }
    return false;
  }

  async function buy() {
    const plan = plans?.[selected];
    if (!plan) return;
    setBusy('buy');
    setError(null);
    try {
      if (!(await purchases.buy(plan))) return; // cancelled
      if (!(await confirmWithServer())) {
        setError('Payment went through, but we couldn’t confirm it yet. Tap “Restore purchases” in a minute.');
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  }

  async function restore() {
    setBusy('restore');
    setError(null);
    try {
      await purchases.restore();
      if (!(await confirmWithServer())) setError('No active purchase found for this store account.');
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  }

  // ---------- Already Pro ----------
  if (isPro) {
    const kind = access?.kind;
    return (
      <ScrollView style={{ backgroundColor: c.bg }} contentContainerStyle={{ padding: 20, gap: 14 }}>
        <Title>You’re on Pro 🎉</Title>
        <Card>
          <Body style={{ fontWeight: '700' }}>
            {kind === 'lifetime'
              ? 'Lifetime access'
              : kind === 'subscription'
                ? `Subscription · ${access?.will_renew === false ? 'ends' : 'renews'} ${formatDate(access?.expires_at)}`
                : 'Complimentary access'}
          </Body>
          {access?.management_url ? (
            <Button
              variant="ghost"
              title="Manage subscription"
              onPress={() => Linking.openURL(access.management_url!)}
            />
          ) : null}
        </Card>
        {jottings.length ? (
          <Button
            title={`Upload my ${jottings.length} note(s) from this phone`}
            onPress={() => router.replace('/inbox')}
          />
        ) : null}
        <Button title="Start capturing" variant="secondary" onPress={() => router.replace('/')} />
      </ScrollView>
    );
  }

  // ---------- Paywall ----------
  return (
    <ScrollView style={{ backgroundColor: c.bg }} contentContainerStyle={{ padding: 20, gap: 14 }}>
      <View style={{ gap: 6 }}>
        <Title>Forge Capture Pro</Title>
        <Body muted>
          Jotting notes on your phone is free forever. Go Pro to turn them into real, estimated work in Buildly Labs.
        </Body>
      </View>

      <Card>
        {FEATURES.map(([icon, title, detail]) => (
          <View key={title} style={{ flexDirection: 'row', gap: 12, alignItems: 'flex-start' }}>
            <Body style={{ fontSize: 20 }}>{icon}</Body>
            <View style={{ flex: 1 }}>
              <Body style={{ fontWeight: '700' }}>{title}</Body>
              <Body muted>{detail}</Body>
            </View>
          </View>
        ))}
      </Card>

      {error ? <Banner tone="danger" text={error} /> : null}

      {!token ? (
        <>
          <Banner text="Create a free account or sign in first — your purchase is tied to your account so it works on all your devices." />
          <Button title="Sign in or create account" onPress={() => router.push('/login')} />
        </>
      ) : !purchases.storeBillingAvailable ? (
        <Banner text="In-app purchases aren’t available in this build. Install Forge Capture from the App Store or Google Play." />
      ) : !serverReady ? (
        <Banner text="Purchases aren’t enabled on this Forge server yet. Ask your admin for access." />
      ) : plans === null ? (
        error ? null : <ActivityIndicator />
      ) : plans.length === 0 ? (
        <Banner text="No plans are available right now. Please try again later." />
      ) : (
        <>
          <Label>Choose a plan</Label>
          {plans.map((plan, i) => (
            <Pressable
              key={plan.pkg.identifier}
              accessibilityRole="radio"
              accessibilityState={{ checked: selected === i }}
              onPress={() => setSelected(i)}
            >
              <Card style={selected === i ? { borderColor: c.primary, borderWidth: 2 } : undefined}>
                <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }}>
                  <View style={{ flex: 1 }}>
                    <Body style={{ fontWeight: '700' }}>
                      {plan.title}
                      {plan.oneTime ? '  · pay once' : ''}
                    </Body>
                    <Body muted>{plan.detail}</Body>
                  </View>
                  <Body style={{ fontWeight: '800', fontSize: 18 }}>{plan.price}</Body>
                </View>
              </Card>
            </Pressable>
          ))}
          <Button
            title={plans[selected]?.oneTime ? `Buy for ${plans[selected].price}` : 'Subscribe'}
            onPress={buy}
            loading={busy === 'buy'}
            disabled={!!busy}
          />
          {!plans[selected]?.oneTime ? (
            <Body muted style={{ fontSize: 12, textAlign: 'center' }}>
              Payment is charged to your {Platform.OS === 'ios' ? 'Apple ID' : 'Google Play'} account. The
              subscription renews automatically unless cancelled at least 24 hours before the end of the current
              period. Manage or cancel anytime in your account settings.
            </Body>
          ) : null}
        </>
      )}

      {token && purchases.storeBillingAvailable ? (
        <Button title="Restore purchases" variant="ghost" onPress={restore} loading={busy === 'restore'} disabled={!!busy} />
      ) : null}

      <View style={{ flexDirection: 'row', justifyContent: 'center', gap: 20 }}>
        {extra.termsUrl ? (
          <Pressable onPress={() => Linking.openURL(extra.termsUrl!)}>
            <Body muted style={{ fontSize: 13, textDecorationLine: 'underline' }}>Terms</Body>
          </Pressable>
        ) : null}
        {extra.privacyUrl ? (
          <Pressable onPress={() => Linking.openURL(extra.privacyUrl!)}>
            <Body muted style={{ fontSize: 13, textDecorationLine: 'underline' }}>Privacy</Body>
          </Pressable>
        ) : null}
      </View>
      <Button title="Not now — keep jotting for free" variant="ghost" onPress={() => router.back()} />
    </ScrollView>
  );
}
