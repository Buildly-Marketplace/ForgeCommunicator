import * as Device from 'expo-device';
import * as Linking from 'expo-linking';
import { router } from 'expo-router';
import * as WebBrowser from 'expo-web-browser';
import { useState } from 'react';
import { KeyboardAvoidingView, Platform, Pressable, ScrollView, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Banner, Body, Button, Field, Label, Title, useColors } from '../components/ui';
import { Api, normalizeServerUrl } from '../lib/api';
import { useSession } from '../lib/session';

WebBrowser.maybeCompleteAuthSession();

export default function Login() {
  const c = useColors();
  const { serverUrl, signIn, setServerUrl } = useSession();
  const [server, setServer] = useState(serverUrl);
  const [showServer, setShowServer] = useState(false);
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [name, setName] = useState('');
  const [busy, setBusy] = useState<'labs' | 'email' | null>(null);
  const [error, setError] = useState<string | null>(null);

  const deviceName = Device.deviceName ?? Device.modelName ?? 'Forge Capture';

  async function withLabs() {
    setError(null);
    setBusy('labs');
    try {
      const url = normalizeServerUrl(server);
      await setServerUrl(url);
      const { auth_url } = await new Api(url, null).oauthStart('buildly');
      const result = await WebBrowser.openAuthSessionAsync(auth_url, 'forgecapture://oauth');
      if (result.type !== 'success') return;
      const token = Linking.parse(result.url).queryParams?.token;
      if (typeof token !== 'string' || !token) throw new Error('Sign-in did not return a token');
      await signIn(url, token);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  }

  async function withEmail() {
    setError(null);
    if (!email.trim() || !password) return setError('Enter your email and password');
    if (mode === 'register' && !name.trim()) return setError('Enter your name');
    setBusy('email');
    try {
      const url = normalizeServerUrl(server);
      const client = new Api(url, null);
      const res =
        mode === 'login'
          ? await client.login(email.trim(), password, deviceName)
          : await client.register(email.trim(), password, name.trim(), deviceName);
      await signIn(url, res.token);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  }

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: c.bg }}>
      <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
        <ScrollView contentContainerStyle={{ padding: 24, gap: 16, flexGrow: 1, justifyContent: 'center' }}>
          <View style={{ gap: 6, marginBottom: 8 }}>
            <Title>Forge Capture</Title>
            <Body muted>
              Sign in to save your notes, get AI estimates and send them to Buildly Labs. Jotting notes on this phone
              works without an account.
            </Body>
          </View>

          {error ? <Banner tone="danger" text={error} /> : null}

          <Button title="Continue with Buildly Labs" onPress={withLabs} loading={busy === 'labs'} disabled={!!busy} />

          <Body muted style={{ textAlign: 'center' }}>or</Body>

          {mode === 'register' ? (
            <Field placeholder="Your name" value={name} onChangeText={setName} textContentType="name" />
          ) : null}
          <Field
            placeholder="Email"
            value={email}
            onChangeText={setEmail}
            autoCapitalize="none"
            autoCorrect={false}
            keyboardType="email-address"
            textContentType="emailAddress"
          />
          <Field
            placeholder="Password"
            value={password}
            onChangeText={setPassword}
            secureTextEntry
            textContentType={mode === 'login' ? 'password' : 'newPassword'}
            onSubmitEditing={withEmail}
          />
          <Button
            title={mode === 'login' ? 'Sign in' : 'Create account'}
            variant="secondary"
            onPress={withEmail}
            loading={busy === 'email'}
            disabled={!!busy}
          />
          <Button
            variant="ghost"
            title={mode === 'login' ? 'New here? Create an account' : 'Have an account? Sign in'}
            onPress={() => setMode(mode === 'login' ? 'register' : 'login')}
          />

          <Button variant="ghost" title="Not now" onPress={() => router.back()} />

          <Pressable onPress={() => setShowServer(!showServer)} accessibilityRole="button">
            <Body muted style={{ textAlign: 'center', fontSize: 13 }}>
              Server: {normalizeServerUrl(server)} {showServer ? '▴' : '▾'}
            </Body>
          </Pressable>
          {showServer ? (
            <View style={{ gap: 6 }}>
              <Label>Forge server URL</Label>
              <Field
                value={server}
                onChangeText={setServer}
                autoCapitalize="none"
                autoCorrect={false}
                keyboardType="url"
                placeholder="https://comms.buildly.io"
              />
            </View>
          ) : null}
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}
