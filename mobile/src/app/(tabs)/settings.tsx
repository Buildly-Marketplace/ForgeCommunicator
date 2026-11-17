import { router } from 'expo-router';
import { ScrollView, View } from 'react-native';
import * as Application from 'expo-application';

import { Banner, Body, Button, Card, Chip, Label, Row, Screen } from '../../components/ui';
import { useSession } from '../../lib/session';

export default function Settings() {
  const { user, token, bootstrap, workspace, selectWorkspace, serverUrl, signOut, refreshBootstrap, access, isPro } =
    useSession();

  if (!token) {
    return (
      <Screen>
        <ScrollView contentContainerStyle={{ padding: 16, gap: 14 }}>
          <Card>
            <Label>Not signed in</Label>
            <Body>Your notes are saved on this phone. Sign in to sync them, get AI estimates and send them to Labs.</Body>
            <Button title="Sign in or create account" onPress={() => router.push('/login')} />
          </Card>
          <Button title="See Pro plans" variant="ghost" onPress={() => router.push('/paywall')} />
        </ScrollView>
      </Screen>
    );
  }

  const planLabel = !access
    ? '—'
    : !access.required
      ? 'Pro · included'
      : access.active
        ? access.kind === 'lifetime'
          ? 'Pro · lifetime'
          : access.kind === 'grant'
            ? 'Pro · complimentary'
            : `Pro · ${access.will_renew === false ? 'ends' : 'renews'} ${access.expires_at ? new Date(access.expires_at).toLocaleDateString() : ''}`
        : 'Free · notes on this phone';

  return (
    <Screen>
      <ScrollView contentContainerStyle={{ padding: 16, gap: 14 }}>
        <Card>
          <Label>Signed in as</Label>
          <Body style={{ fontWeight: '700' }}>{user?.display_name ?? '—'}</Body>
          <Body muted>{user?.email}</Body>
          <Body muted>{serverUrl}</Body>
        </Card>

        <Card>
          <Label>Plan</Label>
          <Body style={{ fontWeight: '700' }}>{planLabel}</Body>
          <Button
            title={isPro ? 'Manage plan' : 'Go Pro'}
            variant={isPro ? 'ghost' : 'primary'}
            onPress={() => router.push('/paywall')}
          />
        </Card>

        <View style={{ gap: 8 }}>
          <Label>Workspace</Label>
          <Row>
            {bootstrap?.workspaces.map((w) => (
              <Chip key={w.id} label={w.name} active={workspace?.id === w.id} onPress={() => selectWorkspace(w.id)} />
            ))}
          </Row>
          <Button title="Refresh" variant="ghost" onPress={() => refreshBootstrap().catch(() => undefined)} />
        </View>

        <Card>
          <Label>Connections</Label>
          <Row>
            <Chip
              label={bootstrap?.user_labs_connected ? 'Buildly Labs: connected' : 'Buildly Labs: not linked'}
              tone={bootstrap?.user_labs_connected ? 'success' : 'warn'}
            />
            <Chip
              label={bootstrap?.ai_configured ? 'AI estimates: on' : 'AI estimates: workspace agent / basic'}
              tone={bootstrap?.ai_configured ? 'success' : undefined}
            />
          </Row>
          {!bootstrap?.user_labs_connected ? (
            <Banner text="Sign out and use “Continue with Buildly Labs” to link your Labs account." />
          ) : null}
        </Card>

        <Button title="Sign out" variant="danger" onPress={signOut} />
        <Body muted style={{ textAlign: 'center', fontSize: 12 }}>
          Forge Capture {Application.nativeApplicationVersion ?? ''}
        </Body>
      </ScrollView>
    </Screen>
  );
}
