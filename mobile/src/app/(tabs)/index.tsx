import * as Application from 'expo-application';
import * as Crypto from 'expo-crypto';
import * as Device from 'expo-device';
import * as Haptics from 'expo-haptics';
import * as ImagePicker from 'expo-image-picker';
import { router, useFocusEffect } from 'expo-router';
import { useCallback, useState } from 'react';
import { Alert, Image, KeyboardAvoidingView, Platform, Pressable, ScrollView, Text, View } from 'react-native';

import { Banner, Body, Button, Chip, Field, Label, Row, Screen, useColors } from '../../components/ui';
import { useSession } from '../../lib/session';
import type { IdeaKind, PendingCapture, Product } from '../../lib/types';

const MAX_PHOTOS = 6;
type Photo = PendingCapture['photos'][number];

const KINDS: { kind: IdeaKind; label: string; placeholder: string }[] = [
  { kind: 'idea', label: '💡 Idea', placeholder: 'What should we build? A sentence is enough…' },
  { kind: 'bug', label: '🐞 Bug', placeholder: 'What went wrong? What did you expect to happen?' },
  { kind: 'feedback', label: '💬 Feedback', placeholder: 'What’s on your mind about this product?' },
];

function toPhoto(asset: ImagePicker.ImagePickerAsset, i: number): Photo {
  const type = asset.mimeType ?? 'image/jpeg';
  const ext = type.split('/')[1] ?? 'jpg';
  return { uri: asset.uri, name: asset.fileName ?? `capture-${Date.now()}-${i}.${ext}`, type };
}

export default function CaptureScreen() {
  const c = useColors();
  const { api, token, workspace, bootstrap, capture, pending, isPro } = useSession();
  const [kind, setKind] = useState<IdeaKind>('idea');
  const [body, setBody] = useState('');
  const [appName, setAppName] = useState('');
  const [photos, setPhotos] = useState<Photo[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [productId, setProductId] = useState<number | null>(null);
  const [busy, setBusy] = useState<'save' | 'estimate' | null>(null);
  const [notice, setNotice] = useState<{ text: string; tone: 'success' | 'warn' | 'danger' } | null>(null);

  // Free notes keep photos on the phone; Pro uploads need server storage
  const uploadsEnabled = !isPro || (bootstrap?.uploads_enabled ?? true);

  useFocusEffect(
    useCallback(() => {
      if (!workspace || !token) return;
      api
        .products(workspace.id)
        .then((list) => {
          setProducts(list);
          setProductId((cur) => (cur && list.some((p) => p.id === cur) ? cur : null));
        })
        .catch(() => undefined); // offline: keep last list
    }, [api, workspace, token]),
  );

  async function addPhotos(source: 'camera' | 'library') {
    const room = MAX_PHOTOS - photos.length;
    if (room <= 0) return;
    const perm =
      source === 'camera'
        ? await ImagePicker.requestCameraPermissionsAsync()
        : await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (!perm.granted) {
      Alert.alert('Permission needed', `Allow ${source === 'camera' ? 'camera' : 'photo'} access in Settings to attach images.`);
      return;
    }
    const opts: ImagePicker.ImagePickerOptions = { mediaTypes: ['images'], quality: 0.7 };
    const result =
      source === 'camera'
        ? await ImagePicker.launchCameraAsync(opts)
        : await ImagePicker.launchImageLibraryAsync({ ...opts, allowsMultipleSelection: true, selectionLimit: room });
    if (result.canceled) return;
    setPhotos((cur) => [...cur, ...result.assets.slice(0, room).map(toPhoto)]);
  }

  function reset() {
    setBody('');
    setAppName('');
    setPhotos([]);
  }

  async function submit(estimate: boolean) {
    if (!body.trim() && photos.length === 0) {
      setNotice({ text: 'Write something or add a photo first.', tone: 'warn' });
      return;
    }
    setNotice(null);
    setBusy(estimate ? 'estimate' : 'save');
    const context: Record<string, string> = {
      device_model: Device.modelName ?? '',
      os: `${Device.osName ?? Platform.OS} ${Device.osVersion ?? ''}`.trim(),
      captured_with: `Forge Capture ${Application.nativeApplicationVersion ?? ''}`.trim(),
    };
    if (appName.trim()) context.app_name = appName.trim();

    const item: PendingCapture = {
      clientId: Crypto.randomUUID(),
      workspaceId: workspace?.id ?? null,
      productId,
      kind,
      body: body.trim(),
      context,
      photos,
      createdAt: new Date().toISOString(),
    };
    try {
      const outcome = await capture(item);
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success).catch(() => undefined);
      reset();
      if (outcome.kind === 'local') {
        setNotice({ text: 'Saved on this phone. Find it under My ideas.', tone: 'success' });
        if (estimate) router.push('/paywall');
      } else if (outcome.kind === 'queued') {
        setNotice({ text: 'Saved. It will upload when you’re back online.', tone: 'warn' });
      } else if (estimate) {
        router.push({ pathname: '/idea/[id]', params: { id: String(outcome.idea.id), refine: '1' } });
      } else {
        setNotice({ text: 'Captured! Find it under My ideas.', tone: 'success' });
      }
    } catch (e) {
      setNotice({ text: e instanceof Error ? e.message : String(e), tone: 'danger' });
    } finally {
      setBusy(null);
    }
  }

  const kindMeta = KINDS.find((k) => k.kind === kind)!;

  return (
    <Screen>
      <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
        <ScrollView contentContainerStyle={{ padding: 16, gap: 14 }} keyboardShouldPersistTaps="handled">
          <Row>
            {KINDS.map((k) => (
              <Chip key={k.kind} label={k.label} active={kind === k.kind} onPress={() => setKind(k.kind)} />
            ))}
          </Row>

          <Field
            multiline
            autoFocus
            value={body}
            onChangeText={setBody}
            placeholder={kindMeta.placeholder}
            style={{ minHeight: 160, textAlignVertical: 'top' }}
            accessibilityLabel="Your note"
          />

          {kind === 'bug' ? (
            <Field
              value={appName}
              onChangeText={setAppName}
              placeholder="Which app or page? (optional)"
              accessibilityLabel="Which app or page"
            />
          ) : null}

          <View style={{ gap: 8 }}>
            <Label>Photos & screenshots</Label>
            <Row>
              <Button
                variant="secondary"
                title="📷 Camera"
                onPress={() => addPhotos('camera')}
                disabled={!uploadsEnabled || photos.length >= MAX_PHOTOS}
                style={{ flex: 1 }}
              />
              <Button
                variant="secondary"
                title="🖼 Screenshot"
                accessibilityLabel="Attach a screenshot or photo from your library"
                onPress={() => addPhotos('library')}
                disabled={!uploadsEnabled || photos.length >= MAX_PHOTOS}
                style={{ flex: 1 }}
              />
            </Row>
            {!uploadsEnabled ? <Body muted>Image uploads aren’t enabled on this server.</Body> : null}
            {photos.length ? (
              <ScrollView horizontal contentContainerStyle={{ gap: 8 }}>
                {photos.map((p, i) => (
                  <Pressable
                    key={p.uri}
                    onPress={() => setPhotos((cur) => cur.filter((_, j) => j !== i))}
                    accessibilityLabel={`Remove photo ${i + 1}`}
                  >
                    <Image source={{ uri: p.uri }} style={{ width: 84, height: 84, borderRadius: 10 }} />
                    <Text
                      style={{
                        position: 'absolute', top: 4, right: 4, color: '#fff', backgroundColor: '#0009',
                        borderRadius: 10, paddingHorizontal: 6, fontWeight: '700',
                      }}
                    >
                      ✕
                    </Text>
                  </Pressable>
                ))}
              </ScrollView>
            ) : null}
          </View>

          {workspace ? (
            <View style={{ gap: 8 }}>
              <Label>Product · {workspace.name}</Label>
              {products.length ? (
                <Row>
                  <Chip label="Not sure" active={productId === null} onPress={() => setProductId(null)} />
                  {products.map((p) => (
                    <Chip key={p.id} label={p.name} active={productId === p.id} onPress={() => setProductId(p.id)} />
                  ))}
                </Row>
              ) : (
                <Body muted>No products yet — sync them from Labs on the Products tab.</Body>
              )}
            </View>
          ) : null}

          {notice ? <Banner text={notice.text} tone={notice.tone} /> : null}
          {pending.length ? (
            <Body muted>{pending.length} capture(s) waiting to upload.</Body>
          ) : null}

          {isPro ? (
            <>
              <Button
                title="✨ Capture & estimate"
                onPress={() => submit(true)}
                loading={busy === 'estimate'}
                disabled={!!busy}
              />
              <Button
                title="Just save it"
                variant="secondary"
                onPress={() => submit(false)}
                loading={busy === 'save'}
                disabled={!!busy}
              />
              <Body muted style={{ textAlign: 'center', fontSize: 13, color: c.muted }}>
                Estimating turns your note into features & issues with developer and AI time estimates. Nothing goes
                to Labs until you review it.
              </Body>
            </>
          ) : (
            <>
              <Button title="Save note" onPress={() => submit(false)} loading={busy === 'save'} disabled={!!busy} />
              <Button
                title="✨ Estimate & send to Labs · Pro"
                variant="secondary"
                onPress={() => submit(true)}
                loading={busy === 'estimate'}
                disabled={!!busy}
              />
              <Body muted style={{ textAlign: 'center', fontSize: 13, color: c.muted }}>
                Notes are free and stay on this phone. Pro saves them to your account, breaks them into features &
                issues with developer and AI estimates, and sends them to Buildly Labs.
              </Body>
            </>
          )}
        </ScrollView>
      </KeyboardAvoidingView>
    </Screen>
  );
}
