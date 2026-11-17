import { router, useFocusEffect } from 'expo-router';
import { useCallback, useState } from 'react';
import { Alert, FlatList, Image, Pressable, RefreshControl, ScrollView, View } from 'react-native';

import { Banner, Body, Button, Card, Chip, Empty, Label, Row, STATUS_LABEL, Screen } from '../../components/ui';
import { useSession } from '../../lib/session';
import type { Idea, PendingCapture } from '../../lib/types';

const KIND_ICON: Record<string, string> = { idea: '💡', bug: '🐞', feedback: '💬' };
const STATUS_TONE: Record<string, 'success' | 'warn' | 'danger' | undefined> = {
  submitted: 'success',
  refined: 'warn',
  failed: 'danger',
};

export default function Inbox() {
  const { api, token, workspace, pending, flush, jottings, isPro, deleteJotting, uploadJotting } = useSession();
  const [uploading, setUploading] = useState<string | null>(null);
  const [ideas, setIdeas] = useState<Idea[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!token) return; // signed out: only notes on this phone
    setLoading(true);
    setError(null);
    try {
      if (pending.length && isPro) await flush();
      setIdeas(await api.ideas(workspace?.id));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [api, token, isPro, workspace?.id]);

  useFocusEffect(
    useCallback(() => {
      load();
    }, [load]),
  );

  async function upload(j: PendingCapture) {
    if (!isPro) {
      router.push('/paywall');
      return;
    }
    if (j.productId == null) {
      // Ideas belong to a product: ask which one before uploading
      router.push({ pathname: '/choose-product', params: { clientId: j.clientId } });
      return;
    }
    setUploading(j.clientId);
    setError(null);
    try {
      const idea = await uploadJotting(j.clientId);
      if (idea) router.push({ pathname: '/idea/[id]', params: { id: String(idea.id), refine: '1' } });
      else load();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setUploading(null);
    }
  }

  function confirmDelete(j: PendingCapture) {
    Alert.alert('Delete this note?', 'It only exists on this phone.', [
      { text: 'Cancel', style: 'cancel' },
      { text: 'Delete', style: 'destructive', onPress: () => deleteJotting(j.clientId) },
    ]);
  }

  return (
    <Screen>
      <FlatList
        data={ideas}
        keyExtractor={(i) => String(i.id)}
        contentContainerStyle={{ padding: 16, gap: 10 }}
        refreshControl={<RefreshControl refreshing={loading} onRefresh={load} />}
        ListHeaderComponent={
          <View style={{ gap: 10 }}>
            {error ? <Banner tone="danger" text={error} /> : null}
            {jottings.length ? <Label>On this phone · {jottings.length}</Label> : null}
            {[...jottings].reverse().map((j) => (
              <Card key={j.clientId}>
                <Body numberOfLines={4}>
                  {KIND_ICON[j.kind]} {j.body || `${j.photos.length} photo(s)`}
                </Body>
                {j.photos.length ? (
                  <ScrollView horizontal contentContainerStyle={{ gap: 6 }}>
                    {j.photos.map((p) => (
                      <Image key={p.uri} source={{ uri: p.uri }} style={{ width: 56, height: 56, borderRadius: 8 }} />
                    ))}
                  </ScrollView>
                ) : null}
                <Body muted style={{ fontSize: 12 }}>{new Date(j.createdAt).toLocaleString()}</Body>
                <Row>
                  <Button
                    title={isPro ? '✨ Upload & estimate' : '✨ Estimate · Pro'}
                    variant="secondary"
                    onPress={() => upload(j)}
                    loading={uploading === j.clientId}
                    disabled={!!uploading || (isPro && !workspace)}
                    style={{ flex: 1 }}
                  />
                  <Button title="Delete" variant="ghost" onPress={() => confirmDelete(j)} />
                </Row>
              </Card>
            ))}
            {(jottings.length && (ideas.length || pending.length)) ? <Label>Saved to your account</Label> : null}
            {pending.map((p) => (
              <Card key={p.clientId}>
                <Body numberOfLines={2}>
                  {KIND_ICON[p.kind]} {p.body || `${p.photos.length} photo(s)`}
                </Body>
                <Row>
                  <Chip label="Waiting to upload" tone="warn" />
                  {p.lastError ? <Body muted numberOfLines={1}>{p.lastError}</Body> : null}
                </Row>
              </Card>
            ))}
          </View>
        }
        ListEmptyComponent={
          loading || pending.length || jottings.length ? undefined : (
            <Empty title="No captures yet" hint="Ideas and bugs you jot down on the Capture tab show up here." />
          )
        }
        renderItem={({ item }) => {
          const bd = item.breakdown;
          return (
            <Pressable
              accessibilityRole="button"
              onPress={() => router.push({ pathname: '/idea/[id]', params: { id: String(item.id) } })}
            >
              <Card>
                <Body style={{ fontWeight: '700' }} numberOfLines={2}>
                  {KIND_ICON[item.kind]} {item.title || item.body || 'Photo capture'}
                </Body>
                {item.title && item.body ? (
                  <Body muted numberOfLines={2}>
                    {item.body}
                  </Body>
                ) : null}
                <Row>
                  <Chip label={STATUS_LABEL[item.status] ?? item.status} tone={STATUS_TONE[item.status]} />
                  {item.product_name ? <Chip label={item.product_name} /> : null}
                  {bd ? <Chip label={`${bd.items.length} items · ${bd.totals.points} pts`} /> : null}
                  {item.attachments.length ? <Chip label={`📎 ${item.attachments.length}`} /> : null}
                </Row>
              </Card>
            </Pressable>
          );
        }}
      />
    </Screen>
  );
}
